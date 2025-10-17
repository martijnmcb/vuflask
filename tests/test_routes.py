from io import BytesIO


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

    from extensions import db
    from models import StudentSubmission

    with app.app_context():
        submission = (
            db.session.query(StudentSubmission)
            .filter_by(assignment_id=assignment_id)
            .one()
        )
        assert submission.summary == "Student summary via gpt-3.5-turbo"
        assert submission.summary_model == "gpt-3.5-turbo"
