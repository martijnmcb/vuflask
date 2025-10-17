# DiaLoque - AI Teaching Platform

DiaLoque is a teaching lab application for Vrije Universiteit Amsterdam that lets students explore responsible AI mobility scenarios while lecturers manage access, data connections, and governance workflows. The project doubles as an instructional example for AI-assisted software education.

## Architecture Overview
- `app.py` provides the Flask application factory, registers blueprints, and offers a guarded `/init` seeding route.
- `blueprints/` contains feature modules:
  - `auth` for login/logout flows,
  - `main` for the homepage and student-facing routes,
  - `admin` for instructor tooling at `/beheer/`.
- `models.py` defines SQLAlchemy models (`User`, `Role`, `UserProject`, `ConnectionSetting`, `ConnectionProfile`) and helpers for password hashing.
- `extensions.py` initialises shared instances (SQLAlchemy, Flask-Migrate, Flask-Login).
- `templates/` and `static/` host the refreshed DiaLoque UI, including the AI-themed homepage (`templates/main_home.html`) and supporting styles in `static/style.css`.
- `config.py` loads settings from environment variables via `python-dotenv`; local SQLite data lives in `instance/app.db`.
- `tests/` contains pytest route smoke tests that use the application factory fixture (`PYTHONPATH=. pytest`).

## Technology Stack
| Component | Version |
|-----------|---------|
| Python | 3.13.5 |
| Flask | 3.1.2 |
| Flask-Login | 0.6.3 |
| Flask-WTF | 1.2.2 |
| Flask-Migrate | 4.1.0 |
| Flask-SQLAlchemy | 3.1.1 |
| SQLAlchemy | 2.0.44 |
| python-dotenv | 1.1.1 |
| passlib | 1.7.4 |
| pyodbc | 5.2.0 |
| pytest | 8.4.2 |
| gunicorn | 23.0.0 |
| waitress | 3.0.2 |

## Getting Started
1. **Create / activate the virtual environment** (existing project uses `venv/`):
   ```bash
   python3.13 -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```
2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Configure environment variables** (`.env` in project root):
   ```env
   SECRET_KEY=change-me
   SQLALCHEMY_DATABASE_URI=sqlite:///instance/app.db
   FLASK_APP=app:create_app
   FLASK_DEBUG=1           # optional during development
   INIT_TOKEN=choose-a-secret  # optional, used to guard /init when FLASK_DEBUG!=1
   ADMIN_SEED_PASSWORD=admin123  # optional override for seeded admin user
   ```
4. **Run database migrations / create schema**:
   ```bash
   flask db upgrade
   ```
5. **Seed default roles and admin user** (only in development):
   ```bash
   # With debug on or by providing ?token=<INIT_TOKEN>
   curl http://localhost:5000/init
   ```
6. **Start the development server**:
   ```bash
   flask --app app:create_app run --debug
   # or
   python app.py
   ```
7. **Production entry points**: `gunicorn wsgi:app` (Linux/macOS) or `waitress-serve --listen=0.0.0.0:8000 wsgi:app` (Windows).

## Testing
```bash
source venv/bin/activate
PYTHONPATH=. pytest -q
```
> The `PYTHONPATH=.` prefix ensures the root package is discoverable when running inside the sandbox.

## Recent Decisions (Changelog-lite)
- **Homepage refresh (DiaLoque theme)** – Replaced the previous SmartWheels landing page with an AI teaching hero, roadmap, and CTA tailored to VU cohorts (`templates/main_home.html`, `static/style.css`).
- **Brand rename** – Updated navigation, metadata, and supporting docs to use the DiaLoque name and English copy (`templates/base.html`, `start.md`, documentation).
- **Dark-mode contrast fix** – Tweaked feature card palette for better readability in dark theme (`static/style.css`).
- **Contributor guide** – Added `AGENTS.md` to align new contributors around structure, workflow, and security expectations.
