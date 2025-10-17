from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    session,
    request,
)
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileRequired, FileField
from wtforms import HiddenField, SelectField
from wtforms.validators import DataRequired

from extensions import db
from models import Assignment, StudentSubmission
from services.openai_summarizer import (
    SUMMARY_MODELS,
    SummarizationError,
    summarise_document_content,
)

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
        "Upload case analysis (PDF)",
        validators=[FileRequired(), FileAllowed(["pdf"], "Upload a PDF document")],
    )


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

    assignments = (
        db.session.query(Assignment)
        .order_by(Assignment.created_at.desc())
        .all()
    )
    form_select.assignment_id.choices = [(assn.id, assn.title) for assn in assignments]
    form_upload.model.choices = list(SUMMARY_MODELS)

    active_assignment_id = session.get("active_assignment_id")
    active_assignment_title = session.get("active_assignment_title")
    requested_stage = request.args.get("step")
    stage = session.get("student_stage", 1)

    def _redirect_to_stage(value: int):
        session["student_stage"] = value
        return redirect(url_for("main.student", step=value))

    if requested_stage:
        try:
            requested_stage = int(requested_stage)
        except ValueError:
            requested_stage = 1
        stage = max(1, min(requested_stage, 3))

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

    # Prefill select with current assignment if available
    if active_assignment_id and not form_select.assignment_id.data and assignments:
        form_select.assignment_id.data = active_assignment_id

    form_upload.assignment_id.data = str(active_assignment_id or "")

    active_assignment = None
    assignment_summary_doc = None
    student_submissions = []

    if active_assignment_id:
        active_assignment = db.session.get(Assignment, active_assignment_id)
        if active_assignment:
            assignment_summary_doc = next((doc for doc in active_assignment.documents if doc.slot == 1), None)
            student_submissions = (
                db.session.query(StudentSubmission)
                .filter_by(assignment_id=active_assignment.id, student_id=current_user.id)
                .order_by(StudentSubmission.uploaded_at.desc())
                .all()
            )

    if stage == 2 and not active_assignment:
        return _redirect_to_stage(1)

    if stage == 3 and not student_submissions:
        stage = 2
        session["student_stage"] = 2
        return redirect(url_for("main.student", step=2))

    session["student_stage"] = stage

    return render_template(
        "student_dashboard.html",
        select_form=form_select,
        upload_form=form_upload,
        assignments=assignments,
        active_assignment_title=active_assignment_title,
        active_assignment=active_assignment,
        assignment_summary_doc=assignment_summary_doc,
        student_submissions=student_submissions,
        stage=stage,
    )
