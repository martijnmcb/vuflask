# Handoff Notes

## Current Status
- DiaLoque branding, English copy, and AI-themed homepage live across navigation and docs.
- Lecturer console supports creating assignments, managing four PDF artefacts, replacing documents, deleting assignments, and generating OpenAI summaries for the primary lecturer document.
- Student dashboard implements a three-step workflow: assignment selection, case-analysis upload with automatic summarisation, and review of both lecturer and student summaries.
- Database schema includes foundations for future conversational AI (student submissions + message log tables).

## Open Challenges
- Role seeds remain Dutch (`Beheerder`, `Gebruiker`, `Lezer`); confirm if they should be localised to English throughout the UI and seed script.
- Tests still require `PYTHONPATH=.`; consider adding `pytest.ini` or packaging the app for cleaner invocation.
- Accessibility audit (contrast, keyboard focus) has not been run since the UI refresh.
- SQLAlchemy emits `datetime.utcnow()` deprecation warnings; migrate to timezone-aware timestamps when convenient.

## Next Steps
1. Decide on localisation for role labels and propagate changes to `/init`, forms, and templates.
2. Add CI-friendly test config (e.g., `pytest.ini`) to remove the `PYTHONPATH` requirement.
3. Capture updated screenshots / documentation for the student and lecturer dashboards.
4. Implement LLM conversation flow using `StudentSubmissionMessage` once design is finalised.

## Key Artifacts & Paths
- Lecturer UI: `templates/lecturer_assignments.html`, `templates/lecturer_assignment_detail.html`
- Student UI: `templates/student_dashboard.html`, wizard logic in `blueprints/main/routes.py`
- Summaries & services: `services/openai_summarizer.py`
- Data models: `models.py` (`Assignment*`, `StudentSubmission`, `StudentSubmissionMessage`)
- API bootstrap: `app.py` (`/init` seeding)
- Styles: `static/style.css`
- Docs: `README.md`, `AGENTS.md`, `HANDOFF.md`, `start.md`
- Database migrations (latest):
  - `migrations/versions/b4a14fbb86f9_add_assignments.py`
  - `migrations/versions/95a62308a870_add_assignment_document_summaries.py`
  - `migrations/versions/f18334320412_add_student_submissions.py`
- Local dev DB (ignored): `instance/app.db`

## Tests & Logs
- Command: `source venv/bin/activate && PYTHONPATH=. pytest -q`
  - Latest run: `11 passed in 0.99s`
- Earlier run without `PYTHONPATH` still fails (`ModuleNotFoundError: app`).
- OpenAI interactions are mocked in tests; real usage needs network access + valid `OPENAI_API_KEY`.

## Schemas & Contracts
- `User` / `Role` / `user_roles` – authentication and authorisation, many-to-many.
- `Assignment` – lecturer-defined scenario metadata, relationship to `AssignmentDocument` and `StudentSubmission`.
- `AssignmentDocument` – stored PDF bytes, slot order (1..4), lecturer summary metadata for document 1.
- `StudentSubmission` – student-uploaded PDF, summary text/model/timestamp; future conversation anchor.
- `StudentSubmissionMessage` – conversation log placeholder (role, content, timestamps).
- `/init` – seeds roles and admin user (uses env `INIT_TOKEN` outside debug).

## Environment & Tooling
- Python: 3.13.5 virtual environment located at `venv/` (reuse; do not create `.venv`).
- Core packages (per `pip list` in venv):
  - Flask 3.1.2, Flask-Login 0.6.3, Flask-WTF 1.2.2, email-validator 2.3.0
  - Flask-Migrate 4.1.0, Flask-SQLAlchemy 3.1.1, SQLAlchemy 2.0.44
  - python-dotenv 1.1.1, passlib 1.7.4, pyodbc 5.2.0
  - pytest 8.4.2, gunicorn 23.0.0, waitress 3.0.2
  - openai 2.4.0, pypdf 6.1.1 (install requires network access)
- Required environment variables:
  - `SECRET_KEY`, `SQLALCHEMY_DATABASE_URI` (default SQLite), optional `INIT_TOKEN` & `ADMIN_SEED_PASSWORD`
  - `OPENAI_API_KEY` for lecturer/student summary generation
- External services: OpenAI API (GPT-3.5, GPT-4o-mini, GPT-5) for summaries; ensure key is set before invoking endpoints.

## Additional Notes
- Student workflow uses a session-based wizard (`stage` stored in session); ensure session storage is trusted (Flask secure cookies).
- Binary content (PDFs) lives in database tables—monitor DB size or move to object storage if files grow large.
- Conversational UI is stubbed (Step 4 card) but data model is ready for message history.
- Re-run migrations (`flask db upgrade`) after deploying new code; latest migration adds student submissions + messages.
