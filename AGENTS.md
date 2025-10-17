# Repository Guidelines

## Project Structure & Module Organization
- `app.py`: app factory, local dev server, guarded `/init` bootstrap. Keep production entry points separate.
- `blueprints/`: feature modules (`auth`, `main`, `admin`), each exposing routes in `routes.py` and optional helpers in `__init__.py`.
- `models.py`: SQLAlchemy models for `User`, `Role`, and connection profiles; extend here before running migrations.
- `extensions.py`: shared instances (DB, login manager, migrations) imported by blueprints.
- `config.py` + `.env`: runtime configuration; never hardcode secrets.
- `templates/`, `static/`: Jinja2 templates and assets scoped by blueprint name.
- `tests/`: pytest suites named `test_*.py`; import the factory via `from app import create_app`.
- `instance/`: local-only artifacts (`app.db`); keep out of version control.

## Build, Test, and Development Commands
- `python -m venv .venv && source .venv/bin/activate`: create/activate isolated environment.
- `pip install -r requirements.txt`: install dependencies.
- `flask --app app:create_app run` or `python app.py`: start the dev server at http://localhost:5000.
- `export FLASK_DEBUG=1`: enable debug reloader and tracebacks during dev.
- `pytest -q`: execute the test suite quietly for faster feedback.
- `flask db migrate -m "describe change" && flask db upgrade`: generate and apply DB migrations.

## Coding Style & Naming Conventions
- Follow PEP 8 with 4-space indents and ~100-character lines.
- Use `snake_case` for functions/variables, `PascalCase` for classes, blueprint names mirror folder names.
- Keep routes inside `blueprints/<module>/routes.py`; register blueprints in `app.py` with clear prefixes.
- Prefer descriptive docstrings and lightweight comments before complex logic; default to ASCII text.

## Testing Guidelines
- Tests rely on pytest fixtures; instantiate clients via `create_app().test_client()`.
- Name files `tests/test_<feature>.py`; mirror blueprint structure where practical.
- Target role checks, authentication flows, and admin paths first; add regression tests for reported bugs.

## Commit & Pull Request Guidelines
- Write imperative commit messages scoped by area, e.g., `feat(admin): add user toggle`. Note migrations when relevant.
- PRs should link issues, outline test steps, and include screenshots for template changes.
- Document config impacts (new env vars, secrets) and call out risks or follow-up tasks.

## Security & Configuration Tips
- Load secrets from `.env`; never commit credentials or local SQLite files.
- Protect `/init` outside development by disabling the route or requiring `INIT_TOKEN`.
- For production MSSQL, configure `SQLALCHEMY_DATABASE_URI` with `pyodbc` drivers and verify TLS settings.
