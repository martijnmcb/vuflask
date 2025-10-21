# DiaLoque - AI Teaching Platform

DiaLoque is a teaching lab application for Vrije Universiteit Amsterdam that lets students experiment with responsible AI mobility scenarios while lecturers manage access, artefacts, and governance workflows. The codebase doubles as a teaching example for AI-assisted software development.

## Architecture Overview
- `app.py` – Flask application factory, blueprint registration, and guarded `/init` bootstrap route.
- `blueprints/`
  - `auth` – user authentication views.
  - `main` – homepage plus student workflow (assignment selection, uploads, review, conversation).
  - `admin` – admin console at `/beheer/` for user management.
  - `lecturer` – assignment management, document uploads, summaries, and lecturer prompts at `/lecturer/`.
- `models.py` – SQLAlchemy models for users/roles/projects, assignment artefacts, lecturer prompts, student submissions, and conversation messages.
- `extensions.py` – shared Flask extensions (SQLAlchemy, LoginManager, Alembic).
- `services/openai_summarizer.py` – OpenAI integration and PDF text extraction (supports SDK v0.x and v1.x).
- `services/chat_llm.py` – Conversation helper that builds context (summaries, prompts, history) and calls OpenAI chat models.
- `services/export_pdf.py` – Generates downloadable PDFs combining summaries and chat transcripts.
- `templates/`, `static/` – Jinja UI (AI-themed homepage, lecturer & student dashboards) and custom CSS.
- `config.py` – dotenv-driven configuration (`SECRET_KEY`, DB URI, OpenAI key, etc.).
- `tests/` – pytest smoke tests for routes using the application factory (`PYTHONPATH=. pytest`).

## Technology Stack
| Component | Version |
|-----------|---------|
| Python | 3.13.5 |
| Flask | 3.1.2 |
| Flask-Login | 0.6.3 |
| Flask-WTF | 1.2.2 |
| email-validator | 2.3.0 |
| Flask-Migrate | 4.1.0 |
| Flask-SQLAlchemy | 3.1.1 |
| SQLAlchemy | 2.0.44 |
| python-dotenv | 1.1.1 |
| passlib | 1.7.4 |
| pyodbc | 5.2.0 |
| pytest | 8.4.2 |
| gunicorn | 23.0.0 |
| waitress | 3.0.2 |
| openai | 2.4.0 |
| pypdf | 6.1.1 |
| fpdf2 | 2.7.8 |

## Getting Started
1. **Create / activate virtualenv** (existing project uses `venv/`):
   ```bash
   python3.13 -m venv venv
   source venv/bin/activate            # Windows: venv\Scripts\activate
   ```
2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Configure environment** (`.env` in project root):
   ```env
   SECRET_KEY=change-me
   SQLALCHEMY_DATABASE_URI=sqlite:///instance/app.db
   FLASK_APP=app:create_app
   FLASK_DEBUG=1                 # optional for dev
   INIT_TOKEN=choose-a-secret    # optional for protected /init in non-debug
   ADMIN_SEED_PASSWORD=admin123  # optional override
   OPENAI_API_KEY=sk-...         # required for summaries/chat
   ```
4. **Apply migrations**:
   ```bash
   flask db upgrade
   ```
5. **Seed default roles/admin** (dev only):
   ```bash
   # With debug enabled or ?token=<INIT_TOKEN>
   curl http://localhost:5000/init
   ```
6. **Run locally**:
   ```bash
   flask --app app:create_app run --debug
   # or
   python app.py
   ```
7. **Production entry points**:
   ```bash
   gunicorn wsgi:app
   # Windows-friendly
   waitress-serve --listen=0.0.0.0:8000 wsgi:app
   ```

> Summaries and chat require the `openai` SDK and benefit from `pypdf` for text extraction. Install network-dependent packages ahead of time in restricted environments.

## Testing
```bash
source venv/bin/activate
PYTHONPATH=. pytest -q
```
> `PYTHONPATH=.` is required because the project is not installed as a package.

## Recent Decisions (Changelog-lite)
- **Homepage refresh** – Replaced SmartWheels theming with DiaLoque AI teaching hero/roadmap (`templates/main_home.html`, `static/style.css`).
- **Brand rename** – Updated navigation, metadata, and docs to the DiaLoque name (`templates/base.html`, `start.md`).
- **Dark-mode polish** – Improved feature-card contrast for night mode (`static/style.css`).
- **Lecturer workflow** – Manage four-per-assignment PDFs, OpenAI summaries, and lecturer prompts in the database (`blueprints/lecturer`, `models.Assignment*`, `models.AssignmentPrompt`, `services/openai_summarizer.py`).
- **Student workflow** – Four-step `/student` wizard (select, upload, review, converse) with stored student summaries, lecturer preview, chat restart, and PDF export (`blueprints/main/routes.py`, `templates/student_dashboard.html`, `services/chat_llm.py`, `services/export_pdf.py`).
- **Conversation memory** – Chat history stored in `StudentSubmissionMessage` with metadata for future analysis and prompt seeding.
- **Contributor guide** – Authored `AGENTS.md` for repo structure, style, and security expectations.
