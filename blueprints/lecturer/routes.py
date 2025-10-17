from __future__ import annotations

import os
from datetime import datetime
from io import BytesIO

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    abort,
    send_file,
)
from flask_login import login_required
from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileRequired, FileField
from wtforms import HiddenField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional

from extensions import db
from models import Assignment, AssignmentDocument
from role_required import role_required
from services.openai_summarizer import (
    SUMMARY_MODELS,
    SummarizationError,
    summarise_assignment_document,
)

bp = Blueprint("lecturer", __name__, url_prefix="/lecturer")

DEFAULT_DOC_LABELS = (
    "Instructor brief",
    "Student instructions",
    "Supporting data",
    "Assessment rubric",
)


class AssignmentForm(FlaskForm):
    title = StringField("Assignment title", validators=[DataRequired(), Length(max=200)])
    description = TextAreaField(
        "Description",
        validators=[Optional(), Length(max=2000)],
        render_kw={"rows": 4, "placeholder": "Outline the goal, learning outcomes, or context."},
    )
    doc1_label = StringField("Document 1 label", validators=[Optional(), Length(max=120)])
    doc1_file = FileField(
        "Document 1 (PDF)",
        validators=[FileRequired(), FileAllowed(["pdf"], "Upload a PDF document")],
    )
    doc2_label = StringField("Document 2 label", validators=[Optional(), Length(max=120)])
    doc2_file = FileField(
        "Document 2 (PDF)",
        validators=[FileRequired(), FileAllowed(["pdf"], "Upload a PDF document")],
    )
    doc3_label = StringField("Document 3 label", validators=[Optional(), Length(max=120)])
    doc3_file = FileField(
        "Document 3 (PDF)",
        validators=[FileRequired(), FileAllowed(["pdf"], "Upload a PDF document")],
    )
    doc4_label = StringField("Document 4 label", validators=[Optional(), Length(max=120)])
    doc4_file = FileField(
        "Document 4 (PDF)",
        validators=[FileRequired(), FileAllowed(["pdf"], "Upload a PDF document")],
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_submitted():
            self.doc1_label.data = DEFAULT_DOC_LABELS[0]
            self.doc2_label.data = DEFAULT_DOC_LABELS[1]
            self.doc3_label.data = DEFAULT_DOC_LABELS[2]
            self.doc4_label.data = DEFAULT_DOC_LABELS[3]


class AssignmentUpdateForm(FlaskForm):
    title = StringField("Assignment title", validators=[DataRequired(), Length(max=200)])
    description = TextAreaField(
        "Description",
        validators=[Optional(), Length(max=2000)],
        render_kw={"rows": 4},
    )
    doc1_label = StringField("Document 1 label", validators=[Optional(), Length(max=120)])
    doc1_file = FileField("Replace Document 1", validators=[FileAllowed(["pdf"], "Upload a PDF document")])
    doc2_label = StringField("Document 2 label", validators=[Optional(), Length(max=120)])
    doc2_file = FileField("Replace Document 2", validators=[FileAllowed(["pdf"], "Upload a PDF document")])
    doc3_label = StringField("Document 3 label", validators=[Optional(), Length(max=120)])
    doc3_file = FileField("Replace Document 3", validators=[FileAllowed(["pdf"], "Upload a PDF document")])
    doc4_label = StringField("Document 4 label", validators=[Optional(), Length(max=120)])
    doc4_file = FileField("Replace Document 4", validators=[FileAllowed(["pdf"], "Upload a PDF document")])


class DeleteAssignmentForm(FlaskForm):
    assignment_id = HiddenField(validators=[DataRequired()])


class SummaryForm(FlaskForm):
    assignment_id = HiddenField(validators=[DataRequired()])
    model = SelectField("OpenAI model", choices=[], validators=[DataRequired()])


def _normalise_filename(filename: str, slot: int) -> str:
    if not filename:
        return f"document_{slot}.pdf"
    return os.path.basename(filename)


@bp.route("/assignments", methods=["GET", "POST"])
@login_required
@role_required("Beheerder")
def assignments():
    form = AssignmentForm()
    assignments = (
        db.session.query(Assignment)
        .order_by(Assignment.created_at.desc())
        .all()
    )

    if form.validate_on_submit():
        assignment = Assignment(
            title=form.title.data.strip(),
            description=(form.description.data or "").strip() or None,
        )
        db.session.add(assignment)
        db.session.flush()

        collected = []
        for idx in range(1, 5):
            file_field: FileField = getattr(form, f"doc{idx}_file")
            label_field: StringField = getattr(form, f"doc{idx}_label")
            file_storage = file_field.data
            if not file_storage:
                continue
            file_bytes = file_storage.read()
            file_storage.stream.seek(0)
            document = AssignmentDocument(
                assignment=assignment,
                slot=idx,
                label=(label_field.data or f"Document {idx}").strip() or f"Document {idx}",
                filename=_normalise_filename(file_storage.filename, idx),
                mimetype=file_storage.mimetype or "application/pdf",
                file_size=len(file_bytes),
                content=file_bytes,
            )
            collected.append(document)
            db.session.add(document)

        if len(collected) != 4:
            db.session.rollback()
            flash("Exactly four PDF documents are required per assignment.", "danger")
        else:
            db.session.commit()
            flash("Assignment created successfully.", "success")
            return redirect(url_for("lecturer.assignments"))

    return render_template("lecturer_assignments.html", form=form, assignments=assignments)


@bp.route("/assignments/<int:assignment_id>")
@login_required
@role_required("Beheerder")
def assignment_detail(assignment_id: int):
    assignment = db.session.get(Assignment, assignment_id)
    if not assignment:
        abort(404)
    delete_form = DeleteAssignmentForm(assignment_id=str(assignment.id))
    summary_form = SummaryForm(assignment_id=str(assignment.id))
    summary_form.model.choices = list(SUMMARY_MODELS)
    if not summary_form.model.data:
        summary_form.model.data = SUMMARY_MODELS[0][0]

    primary_doc = next((doc for doc in assignment.documents if doc.slot == 1), None)
    return render_template(
        "lecturer_assignment_detail.html",
        assignment=assignment,
        delete_form=delete_form,
        summary_form=summary_form,
        primary_doc=primary_doc,
    )


def _assignment_document_map(assignment: Assignment) -> dict[int, AssignmentDocument]:
    return {doc.slot: doc for doc in assignment.documents}


@bp.route("/assignments/<int:assignment_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("Beheerder")
def assignment_edit(assignment_id: int):
    assignment = db.session.get(Assignment, assignment_id)
    if not assignment:
        abort(404)

    form = AssignmentUpdateForm(obj=assignment)
    documents = _assignment_document_map(assignment)

    if not documents or len(documents) != 4:
        flash("Assignment is missing documents; please recreate it.", "warning")
        return redirect(url_for("lecturer.assignments"))

    if form.validate_on_submit():
        assignment.title = form.title.data.strip()
        assignment.description = (form.description.data or "").strip() or None

        for idx in range(1, 5):
            document = documents[idx]
            label_field: StringField = getattr(form, f"doc{idx}_label")
            file_field: FileField = getattr(form, f"doc{idx}_file")

            new_label = (label_field.data or document.label or f"Document {idx}").strip()
            document.label = new_label or f"Document {idx}"

            file_storage = file_field.data
            if file_storage:
                file_bytes = file_storage.read()
                file_storage.stream.seek(0)
                document.filename = _normalise_filename(file_storage.filename, idx)
                document.mimetype = file_storage.mimetype or "application/pdf"
                document.file_size = len(file_bytes)
                document.content = file_bytes
                document.uploaded_at = datetime.utcnow()

        db.session.commit()
        flash("Assignment updated successfully.", "success")
        return redirect(url_for("lecturer.assignment_detail", assignment_id=assignment.id))

    # Pre-populate labels with stored values on GET
    if not form.is_submitted():
        for idx in range(1, 5):
            label_field: StringField = getattr(form, f"doc{idx}_label")
            label_field.data = documents[idx].label

    doc_rows = []
    for idx in range(1, 5):
        doc_rows.append({
            "document": documents[idx],
            "label_field": getattr(form, f"doc{idx}_label"),
            "file_field": getattr(form, f"doc{idx}_file"),
        })

    return render_template(
        "lecturer_assignment_edit.html",
        assignment=assignment,
        doc_rows=doc_rows,
        form=form,
    )


@bp.route("/documents/<int:document_id>/download")
@login_required
@role_required("Beheerder")
def download_document(document_id: int):
    document = db.session.get(AssignmentDocument, document_id)
    if not document:
        abort(404)
    return send_file(
        BytesIO(document.content),
        mimetype=document.mimetype or "application/pdf",
        download_name=document.filename,
        as_attachment=True,
    )


@bp.route("/assignments/<int:assignment_id>/delete", methods=["POST"])
@login_required
@role_required("Beheerder")
def assignment_delete(assignment_id: int):
    form = DeleteAssignmentForm()
    if not form.validate_on_submit() or int(form.assignment_id.data) != assignment_id:
        flash("Invalid delete request.", "danger")
        return redirect(url_for("lecturer.assignment_detail", assignment_id=assignment_id))

    assignment = db.session.get(Assignment, assignment_id)
    if not assignment:
        abort(404)

    db.session.delete(assignment)
    db.session.commit()
    flash("Assignment deleted.", "success")
    return redirect(url_for("lecturer.assignments"))


@bp.route("/assignments/<int:assignment_id>/summary", methods=["POST"])
@login_required
@role_required("Beheerder")
def assignment_summary(assignment_id: int):
    assignment = db.session.get(Assignment, assignment_id)
    if not assignment:
        abort(404)

    form = SummaryForm()
    form.model.choices = list(SUMMARY_MODELS)

    if not form.validate_on_submit() or int(form.assignment_id.data) != assignment_id:
        flash("Invalid summary request.", "danger")
        return redirect(url_for("lecturer.assignment_detail", assignment_id=assignment_id))

    primary_doc = next((doc for doc in assignment.documents if doc.slot == 1), None)
    if not primary_doc:
        flash("Assignment is missing the first document.", "warning")
        return redirect(url_for("lecturer.assignment_detail", assignment_id=assignment_id))

    try:
        summarise_assignment_document(primary_doc, form.model.data)
        db.session.commit()
        flash("Summary updated successfully.", "success")
    except SummarizationError as exc:
        db.session.rollback()
        flash(str(exc), "danger")

    return redirect(url_for("lecturer.assignment_detail", assignment_id=assignment_id))
