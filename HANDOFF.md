# Handoff Notes

## Current Status
- DiaLoque branding, English copy, and AI-themed homepage are live across navigation and docs.
- Lecturer console supports full assignment lifecycle (create/edit/delete), four PDF artefacts, OpenAI summaries, and configurable lecturer prompts.
- Student dashboard delivers a four-step wizard: assignment selection, case-analysis upload + summary, review of lecturer/student summaries, and an LLM chat stage with restart + PDF export.
- Database captures submissions, prompts, conversation logs, and summary metadata for future AI analysis.

## Open Challenges
- Role seeds remain Dutch; align localisation strategy (including `/init` and UI copy).
- Tests still require `PYTHONPATH=.`; consider adding `pytest.ini` or packaging the app for CI.
- Accessibility audit (contrast, keyboard paths, screen readers) is pending for refreshed pages.
- SQLAlchemy warns about `datetime.utcnow()`; migrate to timezone-aware timestamps when practical.
- Chat defaults (include summaries, model choice) currently live in code; consider exposing admin controls.

## Next Steps
1. Decide on localisation (role labels, messages) and propagate changes.
2. Add CI-friendly test config to drop the `PYTHONPATH` requirement.
3. Enhance chat experience (persist summary toggles, show active model, optional streaming responses).
4. Capture updated screenshots/docs for lecturer/student workflows.
5. Build richer conversational UX (e.g., rubric-based scoring, feedback export) leveraging `StudentSubmissionMessage` history.

## Key Artifacts & Paths
- Lecturer UI: `templates/lecturer_assignments.html`, `templates/lecturer_assignment_detail.html`
- Lecturer prompts & conversation seeding: `blueprints/lecturer/routes.py`, `models.AssignmentPrompt`
- Student wizard/chat: `templates/student_dashboard.html`, `blueprints/main/routes.py`, `services/chat_llm.py`, `services/export_pdf.py`
- Summaries: `services/openai_summarizer.py`
- Data models: `models.py` (`Assignment*`, `AssignmentPrompt`, `StudentSubmission`, `StudentSubmissionMessage`)
- CLI entrypoint & seeding: `app.py`, `/init`
- Styles: `static/style.css`
- Documentation: `README.md`, `AGENTS.md`, `HANDOFF.md`, `start.md`
- Latest migrations: `migrations/versions/c4e0a60a139e_add_assignment_prompts_and_chat_metadata.py`, `f18334320412_add_student_submissions.py`, `95a62308a870_add_assignment_document_summaries.py`, `b4a14fbb86f9_add_assignments.py`
- Local dev DB (ignored): `instance/app.db`

## Tests & Logs
- `source venv/bin/activate && PYTHONPATH=. pytest -q`
  - Latest run: `14 passed in 1.10s`
- Without `PYTHONPATH`, tests still fail (`ModuleNotFoundError: app`).
- Chat/summarisation tests use monkeypatched OpenAI calls; real usage needs network + valid `OPENAI_API_KEY`.

## Schemas & Contracts
- `User` / `Role` / `user_roles` – authentication/authorisation, many-to-many.
- `Assignment` – lecturer metadata; related to `AssignmentDocument`, `AssignmentPrompt`, `StudentSubmission`.
- `AssignmentDocument` – stored PDFs (slots 1–4), lecturer summary & metadata (slot 1).
- `AssignmentPrompt` – lecturer-authored guidance with optional assistant example responses.
- `StudentSubmission` – student PDF, summary text/model/timestamp; anchor for chat history.
- `StudentSubmissionMessage` – logs conversation turns (role, model, metadata such as summary toggles, token counts).
- `/init` – seeds roles and admin user (guarded by `INIT_TOKEN` when not in debug).

## Environment & Tooling
- Python: 3.13.5 virtualenv at `venv/` (reuse; do not create `.venv`).
- Key packages (from active venv):
  - Flask 3.1.2, Flask-Login 0.6.3, Flask-WTF 1.2.2, email-validator 2.3.0
  - Flask-Migrate 4.1.0, Flask-SQLAlchemy 3.1.1, SQLAlchemy 2.0.44
  - python-dotenv 1.1.1, passlib 1.7.4, pyodbc 5.2.0
  - pytest 8.4.2, gunicorn 23.0.0, waitress 3.0.2
  - openai 2.4.0, pypdf 6.1.1, fpdf2 2.7.8
- Required env vars: `SECRET_KEY`, `SQLALCHEMY_DATABASE_URI` (default SQLite), optional `INIT_TOKEN` & `ADMIN_SEED_PASSWORD`, and `OPENAI_API_KEY` for summaries/chat.
- External service: OpenAI API (GPT-3.5, GPT-4o-mini, GPT-5 models). Ensure key is set before hitting lecturer/student endpoints.

## Additional Notes
- Student wizard relies on session state (`student_stage`, `active_assignment_id`). Flask-signed sessions suffice for dev; consider server-side storage in production.
- Conversation history trims to last 12 messages before hitting the API to manage token cost.
- PDF export sanitises characters unsupported by Helvetica; upgrade to a full Unicode font if future needs require broader character sets.
- Run migrations (`flask db upgrade`) after pulling new code; latest migration adds prompts/chat metadata.
