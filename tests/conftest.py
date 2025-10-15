import os
import pytest


@pytest.fixture(scope="session", autouse=True)
def _set_env():
    os.environ.setdefault("FLASK_DEBUG", "0")
    os.environ.setdefault("SECRET_KEY", "test-secret")
    os.environ.setdefault("SQLALCHEMY_DATABASE_URI", "sqlite:///:memory:")
    yield


@pytest.fixture()
def app():
    from app import create_app
    from extensions import db

    app = create_app()
    with app.app_context():
        db.create_all()
    yield app


@pytest.fixture()
def client(app):
    return app.test_client()

