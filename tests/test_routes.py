from io import BytesIO

from extensions import db
from models import (
    Assignment,
    AssignmentDocument,
    AssignmentPrompt,
    StudentSubmission,
    StudentSubmissionMessage,
)


def _create_assignment(auth_client, app, title="Mobility Forecast Challenge"):
    payload = {
        "title": title,
        "description": "Upload all artefacts for the forecasting assignment.",
        "doc1_label": "Instructor brief",
        "doc2_label": "Student instructions",
        "doc3_label": "Supporting data",
        "doc4_label": "Assessment rubric",
    }
    files = {
        "doc1_file": (BytesIO(b"PDF-one"), "brief.pdf"),
        "doc2_file": (BytesIO(b"PDF-two"), "instructions.pdf"),
        "doc3_file": (BytesIO(b"PDF-three"), "data.pdf"),
        "doc4_file": (BytesIO(b"PDF-four"), "rubric.pdf"),
    }
    response = auth_client.post(
        "/lecturer/assignments",
        data={**payload, **files},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert response.status_code == 200

    from extensions import db
    from models import Assignment

    with app.app_context():
        assignment = db.session.query(Assignment).filter_by(title=title).one()
        return assignment.id


def test_login_page_renders(client):
    resp = client.get("/auth/login")
    assert resp.status_code == 200
    assert b"Gebruikersnaam" in resp.data


def test_home_requires_login(client):
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code in (301, 302)
    assert "/auth/login" in resp.headers.get("Location", "")


def test_admin_requires_login(client):
    resp = client.get("/beheer/", follow_redirects=False)
    assert resp.status_code in (301, 302)
    assert "/auth/login" in resp.headers.get("Location", "")


def test_lecturer_requires_login(client):
    resp = client.get("/lecturer/assignments", follow_redirects=False)
    assert resp.status_code in (301, 302)
    assert "/auth/login" in resp.headers.get("Location", "")


def test_create_assignment_persists_documents(auth_client, app):
    assignment_id = _create_assignment(auth_client, app)

    from extensions import db
    from models import Assignment

    with app.app_context():
        assignment = db.session.get(Assignment, assignment_id)
        assert assignment is not None
        assert len(assignment.documents) == 4
        stored_labels = [doc.label for doc in assignment.documents]
        assert "Instructor brief" in stored_labels
        doc_payload = assignment.documents[0]
        assert doc_payload.file_size == len(b"PDF-one")
        assert doc_payload.base64_content.startswith("UERGL")  # Base64 for "PDF"


def test_edit_assignment_replaces_document(auth_client, app):
    assignment_id = _create_assignment(auth_client, app, title="Demand Modelling Sprint")

    update_payload = {
        "title": "Demand Modelling Sprint v2",
        "description": "Updated brief for cohort B.",
        "doc1_label": "Instructor brief v2",
        "doc2_label": "Student instructions",
        "doc3_label": "Supporting data",
        "doc4_label": "Assessment rubric",
    }
    files = {
        "doc1_file": (BytesIO(b"NEW-PDF"), "brief-v2.pdf"),
    }
    response = auth_client.post(
        f"/lecturer/assignments/{assignment_id}/edit",
        data={**update_payload, **files},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert response.status_code == 200

    from extensions import db
    from models import Assignment

    with app.app_context():
        refreshed = db.session.get(Assignment, assignment_id)
        assert refreshed.title == "Demand Modelling Sprint v2"
        doc1 = next(doc for doc in refreshed.documents if doc.slot == 1)
        assert doc1.label == "Instructor brief v2"
        assert doc1.filename == "brief-v2.pdf"
        assert doc1.file_size == len(b"NEW-PDF")
        assert doc1.base64_content.startswith("TkVXL")  # Base64 for "NEW"


def test_delete_assignment_removes_records(auth_client, app):
    assignment_id = _create_assignment(auth_client, app, title="Deletion Scenario")

    response = auth_client.post(
        f"/lecturer/assignments/{assignment_id}/delete",
        data={"assignment_id": assignment_id},
        follow_redirects=True,
    )
    assert response.status_code == 200

    from extensions import db
    from models import Assignment, AssignmentDocument

    with app.app_context():
        assert db.session.get(Assignment, assignment_id) is None
        assert db.session.query(AssignmentDocument).filter_by(assignment_id=assignment_id).count() == 0


def test_generate_summary_updates_document(monkeypatch, auth_client, app):
    assignment_id = _create_assignment(auth_client, app, title="Summary Scenario")

    def fake_summarise(document, model):
        document.set_summary(f"Summary via {model}", model)
        return None

    monkeypatch.setattr(
        "blueprints.lecturer.routes.summarise_assignment_document",
        fake_summarise,
    )

    response = auth_client.post(
        f"/lecturer/assignments/{assignment_id}/summary",
        data={"assignment_id": assignment_id, "model": "gpt-4o-mini"},
        follow_redirects=True,
    )
    assert response.status_code == 200

    from extensions import db
    from models import AssignmentDocument

    with app.app_context():
        doc1 = (
            db.session.query(AssignmentDocument)
            .filter_by(assignment_id=assignment_id, slot=1)
            .one()
        )
        assert doc1.summary == "Summary via gpt-4o-mini"
        assert doc1.summary_model == "gpt-4o-mini"


def test_student_page_requires_login(client):
    resp = client.get("/student", follow_redirects=False)
    assert resp.status_code in (301, 302)
    assert "/auth/login" in resp.headers.get("Location", "")


def test_student_selects_assignment(auth_client, app):
    assignment_id = _create_assignment(auth_client, app, title="Student Choice")

    resp = auth_client.get("/student")
    assert resp.status_code == 200
    assert b"Student Choice" in resp.data

    post = auth_client.post(
        "/student?step=1",
        data={"select-assignment_id": str(assignment_id)},
        follow_redirects=True,
    )
    assert post.status_code == 200
    assert b"Student Choice" in post.data

    with auth_client.session_transaction() as sess:
        assert sess.get("active_assignment_id") == assignment_id
        assert sess.get("active_assignment_title") == "Student Choice"


def test_student_upload_case_analysis(monkeypatch, auth_client, app):
    assignment_id = _create_assignment(auth_client, app, title="Upload Flow")

    auth_client.post(
        "/student?step=1",
        data={"select-assignment_id": str(assignment_id)},
        follow_redirects=True,
    )

    class DummyResult:
        def __init__(self, text, model):
            self.text = text
            self.model = model

    def fake_summary(content, model):
        return DummyResult(f"Student summary via {model}", model)

    monkeypatch.setattr(
        "blueprints.main.routes.summarise_document_content",
        fake_summary,
    )

    response = auth_client.post(
        "/student?step=2",
        data={
            "upload-assignment_id": str(assignment_id),
            "upload-model": "gpt-3.5-turbo",
            "upload-document": (BytesIO(b"student pdf"), "analysis.pdf"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        submission = (
            db.session.query(StudentSubmission)
            .filter_by(assignment_id=assignment_id)
            .one()
        )
        assert submission.summary == "Student summary via gpt-3.5-turbo"
        assert submission.summary_model == "gpt-3.5-turbo"


def test_lecturer_can_manage_prompts(auth_client, app):
    assignment_id = _create_assignment(auth_client, app, title="Prompted Assignment")

    resp = auth_client.post(
        f"/lecturer/assignments/{assignment_id}/prompts",
        data={
            "title": "Ethics reminder",
            "prompt_text": "Ask the student to reflect on fairness and bias.",
            "example_response": "Consider the impact on vulnerable travellers.",
            "display_order": "1",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200

    resp = auth_client.post(
        f"/lecturer/assignments/{assignment_id}/prompts",
        data={
            "title": "Structure guidance",
            "prompt_text": "Suggest a structure with introduction, analysis, and conclusion.",
            "display_order": "1",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app.app_context():
        prompts = (
            db.session.query(AssignmentPrompt)
            .filter_by(assignment_id=assignment_id)
            .order_by(AssignmentPrompt.display_order.asc())
            .all()
        )
        assert [p.title for p in prompts] == ["Structure guidance", "Ethics reminder"]
        assert [p.display_order for p in prompts] == [1, 2]
        prompt_ids = {p.title: p.id for p in prompts}

    ethics_id = prompt_ids["Ethics reminder"]
    resp = auth_client.post(
        f"/lecturer/prompts/{ethics_id}/order",
        data={"prompt_id": str(ethics_id), "display_order": "1"},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app.app_context():
        prompts = (
            db.session.query(AssignmentPrompt)
            .filter_by(assignment_id=assignment_id)
            .order_by(AssignmentPrompt.display_order.asc())
            .all()
        )
        assert [p.title for p in prompts] == ["Ethics reminder", "Structure guidance"]
        assert [p.display_order for p in prompts] == [1, 2]
        structure_id = prompt_ids["Structure guidance"]

    resp = auth_client.post(
        f"/lecturer/prompts/{structure_id}/delete",
        data={"prompt_id": str(structure_id)},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with app.app_context():
        remaining = (
            db.session.query(AssignmentPrompt)
            .filter_by(assignment_id=assignment_id)
            .order_by(AssignmentPrompt.display_order.asc())
            .all()
        )
        assert len(remaining) == 1
        assert remaining[0].title == "Ethics reminder"
        assert remaining[0].display_order == 1


def test_student_chat_conversation(monkeypatch, auth_client, app):
    assignment_id = _create_assignment(auth_client, app, title="Chat Flow")

    with app.app_context():
        assignment = db.session.get(Assignment, assignment_id)
        prompt_one = AssignmentPrompt(
            assignment=assignment,
            title="Reflection",
            prompt_text="Describe the main accessibility risk you identified.",
            display_order=1,
        )
        prompt_two = AssignmentPrompt(
            assignment=assignment,
            title="Mitigation",
            prompt_text="Suggest one concrete mitigation for the identified risk.",
            display_order=2,
        )
        db.session.add_all([prompt_one, prompt_two])
        db.session.commit()
        prompt_ids = {"first": prompt_one.id, "second": prompt_two.id}

    auth_client.post(
        "/student?step=1",
        data={"select-assignment_id": str(assignment_id)},
        follow_redirects=True,
    )

    class DummySummary:
        def __init__(self, text, model):
            self.text = text
            self.model = model

    monkeypatch.setattr(
        "blueprints.main.routes.summarise_document_content",
        lambda content, model: DummySummary(f"Summary via {model}", model),
    )

    auth_client.post(
        "/student?step=2",
        data={
            "upload-assignment_id": str(assignment_id),
            "upload-model": "gpt-3.5-turbo",
            "upload-document": (BytesIO(b"student pdf"), "analysis.pdf"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
        )

    with app.app_context():
        submission = (
            db.session.query(StudentSubmission)
            .filter_by(assignment_id=assignment_id)
            .one()
        )

    # Load the conversation page to surface the initial lecturer prompt
    stage_four = auth_client.get("/student?step=4", follow_redirects=True)
    assert stage_four.status_code == 200

    from services import chat_llm

    fake_result = chat_llm.ChatResult(
        text="AI assistant reply.",
        model="gpt-4o-mini",
        prompt_tokens=42,
        completion_tokens=21,
        total_tokens=63,
    )

    monkeypatch.setattr(
        chat_llm,
        "generate_chat_response",
        lambda **kwargs: fake_result,
    )

    response = auth_client.post(
        "/student?step=4",
        data={
            "chat-submission_id": str(submission.id),
            "chat-model": "gpt-4o-mini",
            "chat-message": "How can we improve accessibility?",
            "chat-include_lecturer_summary": "y",
            "chat-include_student_summary": "y",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"AI assistant reply" in response.data

    with app.app_context():
        messages = (
            db.session.query(StudentSubmissionMessage)
            .filter_by(submission_id=submission.id)
            .order_by(StudentSubmissionMessage.created_at.asc())
            .all()
        )
        assert len(messages) == 4
        assert messages[0].role == "lecturer"
        first_prompt_ctx = messages[0].get_context()
        assert first_prompt_ctx["prompt_id"] == prompt_ids["first"]
        assert "accessibility risk" in messages[0].content

        assert messages[1].role == "student"
        assert messages[1].content == "How can we improve accessibility?"
        ctx_student = messages[1].get_context()
        assert ctx_student["include_student_summary"] is True
        assert messages[2].role == "assistant"
        assert messages[2].content == "AI assistant reply."
        ctx_assistant = messages[2].get_context()
        assert ctx_assistant["total_tokens"] == 63
        assert messages[3].role == "lecturer"
        second_prompt_ctx = messages[3].get_context()
        assert second_prompt_ctx["prompt_id"] == prompt_ids["second"]
        assert "mitigation" in messages[3].content.lower()


def test_student_download_conversation(monkeypatch, auth_client, app):
    assignment_id = _create_assignment(auth_client, app, title="Download Flow")

    auth_client.post(
        "/student?step=1",
        data={"select-assignment_id": str(assignment_id)},
        follow_redirects=True,
    )

    class DummySummary:
        def __init__(self, text, model):
            self.text = text
            self.model = model

    monkeypatch.setattr(
        "blueprints.main.routes.summarise_document_content",
        lambda content, model: DummySummary(f"Summary via {model}", model),
    )

    auth_client.post(
        "/student?step=2",
        data={
            "upload-assignment_id": str(assignment_id),
            "upload-model": "gpt-3.5-turbo",
            "upload-document": (BytesIO(b"student pdf"), "analysis.pdf"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    with app.app_context():
        submission = (
            db.session.query(StudentSubmission)
            .filter_by(assignment_id=assignment_id)
            .one()
        )

    from services import chat_llm

    monkeypatch.setattr(
        chat_llm,
        "generate_chat_response",
        lambda **kwargs: chat_llm.ChatResult(text="AI assistant reply.", model="gpt-4o-mini"),
    )

    with app.app_context():
        assignment = db.session.get(Assignment, assignment_id)
        prompt = AssignmentPrompt(
            assignment=assignment,
            title="Key risks",
            prompt_text="List the top three risks you see in this project.",
            display_order=1,
        )
        db.session.add(prompt)
        db.session.commit()

    auth_client.get("/student?step=4", follow_redirects=True)
    auth_client.post(
        "/student?step=4",
        data={
            "chat-submission_id": str(submission.id),
            "chat-message": "Summarise key risks",
            "chat-include_lecturer_summary": "y",
            "chat-include_student_summary": "y",
        },
        follow_redirects=True,
    )

    resp = auth_client.get(f"/student/conversation/download?submission_id={submission.id}")
    assert resp.status_code == 200
    assert resp.headers["Content-Type"].startswith("application/pdf")
    assert resp.data.startswith(b"%PDF")
