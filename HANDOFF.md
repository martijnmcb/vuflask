# Handoff Notes

## Current Status
- DiaLoque branding and English messaging now live in navigation, homepage, and documentation.
- Homepage rebuilt with AI teaching visuals and responsive sections; dark-mode contrast tuned for feature cards.
- Documentation refreshed: `README.md`, `AGENTS.md`, and `start.md` aligned with the new positioning and current workflow.

## Open Challenges
- Role seed names are still Dutch ("Beheerder", "Gebruiker", "Lezer"); confirm if they should be Anglicised to match the rest of the UI.
- Tests require `PYTHONPATH=.` when run from the repository root; consider adding a `pytest.ini` or package setup to avoid manual prefixes.
- Evaluate accessibility (contrast ratios, keyboard navigation) after the visual overhaul—no automated audit has been run yet.

## Next Steps
1. Decide on localized vs. English role labels and update seed data plus UI copy accordingly.
2. Add a lightweight configuration (`pytest.ini` or `conftest.py` sys.path tweak) so CI can run `pytest` without environment overrides.
3. Capture updated homepage screenshots for future documentation or course materials once final copy is approved.

## Key Artifacts & Paths
- Homepage template: `templates/main_home.html`
- Global layout: `templates/base.html`
- Styling: `static/style.css`
- Application factory & seed route: `app.py`
- Database models: `models.py`
- Contributor & onboarding docs: `AGENTS.md`, `README.md`, `HANDOFF.md`, `start.md`
- Local development database: `instance/app.db` (do not commit)

## Tests & Logs
- `source venv/bin/activate && PYTHONPATH=. pytest -q`
  - Latest run: `3 passed in 0.34s`
- Prior attempt without `PYTHONPATH` failed (`ModuleNotFoundError: No module named 'app'`).

## Schemas & Contracts
- `models.User`: core auth entity (`first_name`, `last_name`, `email`, `username`, `password_hash`, `roles` many-to-many via `user_roles`).
- `models.Role`: unique role names; currently seeded with Dutch labels.
- `models.UserProject`: associates users with labelled mobility projects (unique per user/project pair).
- `models.ConnectionSetting` / `models.ConnectionProfile`: store SQL Server connectivity metadata including ODBC driver names and TLS toggle via `trust_server_cert`.
- `/init` route (in `app.py`) seeds roles and an admin user (`username=admin`) when run in debug or with valid `INIT_TOKEN`.

## Environment & Tooling
- Python: 3.13.5 (virtual environment at `venv/`).
- Dependency versions (per active venv):
  - Flask 3.1.2, Flask-Login 0.6.3, Flask-WTF 1.2.2, Flask-Migrate 4.1.0, Flask-SQLAlchemy 3.1.1, SQLAlchemy 2.0.44.
  - python-dotenv 1.1.1, passlib 1.7.4, pyodbc 5.2.0.
  - pytest 8.4.2, gunicorn 23.0.0, waitress 3.0.2.
- Reuse the existing `venv`—avoid creating `.venv` or other environments to keep tooling consistent.
- Required env vars: `SECRET_KEY`, `SQLALCHEMY_DATABASE_URI` (defaults to SQLite), optional `INIT_TOKEN` and `ADMIN_SEED_PASSWORD` for `/init`.

## Additional Notes
- Dark-mode theme relies on adding `theme-dark` class to `<html>`; toggled client-side in `templates/base.html`.
- Static assets are pure CSS—no build pipeline required; keep styles ASCII-only unless existing assets demand otherwise.
