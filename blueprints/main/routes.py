from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    session,
    request,
    send_file,
    abort,
)
from markupsafe import Markup, escape
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileRequired, FileField
from wtforms import BooleanField, HiddenField, SelectField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional

from extensions import db
from models import Assignment, StudentSubmission, StudentSubmissionMessage
from services import chat_llm, export_pdf
from services.openai_summarizer import (
    SUMMARY_MODELS,
    SummarizationError,
    summarise_document_content,
)


DEFAULT_CHAT_MODEL = chat_llm.CHAT_MODELS[-1][0] if chat_llm.CHAT_MODELS else "gpt-3.5-turbo"


def _format_summary(text: str | None) -> Markup:
    if not text:
        return Markup("<em>No summary available.</em>")
    sanitized = escape(text.strip()).replace("\r\n", "\n")
    lines = []
    for raw_line in sanitized.split("\n"):
        line = raw_line.strip()
        if not line:
            lines.append("")
            continue
        if line.startswith("- ") or line.startswith("* "):
            content = line[2:].strip()
            lines.append(f"&bull; {content}")
        else:
            lines.append(line)
    html = "<br>".join(lines)
    return Markup(html)

bp = Blueprint("main", __name__)


class AssignmentChoiceForm(FlaskForm):
    assignment_id = SelectField(
        "Choose assignment",
        coerce=int,
        validators=[DataRequired(message="Select an assignment to continue.")],
    )


class SubmissionForm(FlaskForm):
    assignment_id = HiddenField(validators=[DataRequired()])
    model = SelectField("Summary model", choices=[], validators=[DataRequired()])
    document = FileField(
        "Upload case analysis (PDF ONLY)",
        validators=[FileRequired(), FileAllowed(["pdf"], "Upload a PDF document")],
    )


class ConversationForm(FlaskForm):
    submission_id = HiddenField(validators=[DataRequired()])
    message = TextAreaField(
        "Your message",
        validators=[DataRequired(), Length(min=1, max=4000)],
        render_kw={"rows": 3, "placeholder": "Share your question or insight..."},
    )
    include_lecturer_summary = BooleanField("Include lecturer summary", default=True)
    include_student_summary = BooleanField("Include my summary", default=True)


@bp.route("/")
@login_required
def home():
    # Empty home view; no SQL or profile logic
    return render_template("main_home.html")


@bp.route("/student", methods=["GET", "POST"])
@login_required
def student():
    form_select = AssignmentChoiceForm(prefix="select")
    form_upload = SubmissionForm(prefix="upload")
    chat_form = ConversationForm(prefix="chat")

    assignments = (
        db.session.query(Assignment)
        .order_by(Assignment.created_at.desc())
        .all()
    )
    form_select.assignment_id.choices = [(assn.id, assn.title) for assn in assignments]
    form_upload.model.choices = list(SUMMARY_MODELS)
    active_assignment_id = session.get("active_assignment_id")
    active_assignment_title = session.get("active_assignment_title")
    stage = session.get("student_stage", 1)

    if "select-assignment_id" in request.form and form_select.validate_on_submit():
        selected = next((assn for assn in assignments if assn.id == form_select.assignment_id.data), None)
        if not selected:
            flash("Assignment not found. Please try again.", "danger")
            return redirect(url_for("main.student", step=1))
        session["active_assignment_id"] = selected.id
        session["active_assignment_title"] = selected.title
        session["student_stage"] = 2
        flash(f"Assignment '{selected.title}' selected for this session.", "success")
        return redirect(url_for("main.student", step=2))

    if "upload-document" in request.files and form_upload.validate_on_submit():
        try:
            assignment_id = int(form_upload.assignment_id.data)
        except (TypeError, ValueError):
            assignment_id = None

        if not assignment_id:
            flash("Select an assignment before uploading your case analysis.", "warning")
            return redirect(url_for("main.student", step=1))

        assignment = db.session.get(Assignment, assignment_id)
        if not assignment:
            flash("Assignment not found.", "danger")
            return redirect(url_for("main.student", step=1))

        file_storage = form_upload.document.data
        file_bytes = file_storage.read()
        file_storage.stream.seek(0)

        submission = StudentSubmission(
            assignment=assignment,
            student=current_user,
            filename=file_storage.filename or "case-analysis.pdf",
            mimetype=file_storage.mimetype or "application/pdf",
            file_size=len(file_bytes),
            content=file_bytes,
        )
        db.session.add(submission)

        try:
            result = summarise_document_content(file_bytes, form_upload.model.data)
            submission.set_summary(result.text, result.model)
            flash("Case analysis uploaded and summarised.", "success")
        except SummarizationError as exc:
            flash(str(exc), "warning")

        db.session.commit()
        session["active_assignment_id"] = assignment.id
        session["active_assignment_title"] = assignment.title
        session["student_stage"] = 3
        return redirect(url_for("main.student", step=3))

    requested_stage = request.args.get("step")
    if requested_stage:
        try:
            stage = int(requested_stage)
        except ValueError:
            stage = 1

    if active_assignment_id and not form_select.assignment_id.data and assignments:
        form_select.assignment_id.data = active_assignment_id

    active_assignment = db.session.get(Assignment, active_assignment_id) if active_assignment_id else None
    assignment_summary_doc = None
    student_submissions: list[StudentSubmission] = []

    if active_assignment:
        assignment_summary_doc = next((doc for doc in active_assignment.documents if doc.slot == 1), None)
        student_submissions = (
            db.session.query(StudentSubmission)
            .filter_by(assignment_id=active_assignment.id, student_id=current_user.id)
            .order_by(StudentSubmission.uploaded_at.desc())
            .all()
        )

    max_stage_available = 1
    if active_assignment:
        max_stage_available = max(max_stage_available, 2)
    if student_submissions:
        max_stage_available = max(max_stage_available, 4)

    stage = max(1, min(stage, max_stage_available))
    session["student_stage"] = stage

    form_upload.assignment_id.data = str(active_assignment.id if active_assignment else "")

    active_submission = student_submissions[0] if student_submissions else None
    assignment_prompts = active_assignment.prompts if active_assignment else []
    if active_submission:
        chat_form.submission_id.data = str(active_submission.id)
    else:
        chat_form.submission_id.data = ""

    if "chat-message" in request.form and chat_form.validate_on_submit():
        try:
            submission_id = int(chat_form.submission_id.data)
        except (TypeError, ValueError):
            submission_id = None

        submission = db.session.get(StudentSubmission, submission_id) if submission_id else None
        if not submission or submission.student_id != current_user.id:
            flash("Invalid submission.", "danger")
            return redirect(url_for("main.student", step=stage))

        include_lecturer_summary = bool(chat_form.include_lecturer_summary.data)
        include_student_summary = bool(chat_form.include_student_summary.data)

        student_message = StudentSubmissionMessage(
            submission=submission,
            role="student",
            content=chat_form.message.data.strip(),
            model=DEFAULT_CHAT_MODEL,
        )
        student_message.set_context(
            include_lecturer_summary=include_lecturer_summary,
            include_student_summary=include_student_summary,
        )
        db.session.add(student_message)

        try:
            result = chat_llm.generate_chat_response(
                submission=submission,
                user_message=chat_form.message.data,
                model=DEFAULT_CHAT_MODEL,
                include_lecturer_summary=include_lecturer_summary,
                include_student_summary=include_student_summary,
            )
        except chat_llm.ConversationError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
            return redirect(url_for("main.student", step=4))

        assistant_message = StudentSubmissionMessage(
            submission=submission,
            role="assistant",
            content=result.text,
            model=result.model,
        )
        assistant_message.set_context(
            include_lecturer_summary=include_lecturer_summary,
            include_student_summary=include_student_summary,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            total_tokens=result.total_tokens,
        )
        db.session.add(assistant_message)
        db.session.commit()
        session["student_stage"] = 4
        return redirect(url_for("main.student", step=4))

    conversation_messages: list[StudentSubmissionMessage] = []
    if stage >= 4 and active_submission:
        conversation_messages = (
            db.session.query(StudentSubmissionMessage)
            .filter_by(submission_id=active_submission.id)
            .order_by(StudentSubmissionMessage.created_at.asc())
            .all()
        )
    elif stage >= 4 and not active_submission:
        session["student_stage"] = 3
        return redirect(url_for("main.student", step=3))

    return render_template(
        "student_dashboard.html",
        select_form=form_select,
        upload_form=form_upload,
        chat_form=chat_form,
        assignments=assignments,
        active_assignment_title=active_assignment_title,
        active_assignment=active_assignment,
        assignment_summary_doc=assignment_summary_doc,
        student_submissions=student_submissions,
        assignment_prompts=assignment_prompts,
        conversation_messages=conversation_messages,
        active_submission=active_submission,
        stage=stage,
        format_summary=_format_summary,
    )


@bp.route("/student/conversation/restart", methods=["POST"])
@login_required
def restart_conversation():
    submission_id = request.form.get("chat-submission_id", type=int)
    if not submission_id:
        flash("Conversation not found.", "warning")
        return redirect(url_for("main.student", step=3))

    submission = db.session.get(StudentSubmission, submission_id)
    if not submission or submission.student_id != current_user.id:
        abort(404)

    db.session.query(StudentSubmissionMessage).filter_by(submission_id=submission.id).delete()
    db.session.commit()
    flash("Conversation restarted.", "success")
    session["student_stage"] = 4
    return redirect(url_for("main.student", step=4))


@bp.route("/student/conversation/download")
@login_required
def download_conversation():
    submission_id = request.args.get("submission_id", type=int)
    if not submission_id:
        flash("Conversation not found.", "warning")
        return redirect(url_for("main.student", step=4))

    submission = db.session.get(StudentSubmission, submission_id)
    if not submission or submission.student_id != current_user.id:
        abort(404)

    assignment = submission.assignment
    lecturer_doc = next((doc for doc in assignment.documents if doc.slot == 1), None)

    messages = (
        db.session.query(StudentSubmissionMessage)
        .filter_by(submission_id=submission.id)
        .order_by(StudentSubmissionMessage.created_at.asc())
        .all()
    )

    conversation_payload = [
        {
            "role": msg.role,
            "content": msg.content,
            "timestamp": msg.created_at.strftime("%d %b %Y %H:%M") if msg.created_at else None,
        }
        for msg in messages
    ]

    pdf_stream = export_pdf.build_conversation_pdf(
        assignment_title=assignment.title,
        lecturer_summary=lecturer_doc.summary if lecturer_doc else None,
        lecturer_model=lecturer_doc.summary_model if lecturer_doc else None,
        student_summary=submission.summary,
        student_model=submission.summary_model,
        conversation=conversation_payload,
    )

    filename = f"conversation_{assignment.title.replace(' ', '_')}.pdf"
    return send_file(
        pdf_stream,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )
