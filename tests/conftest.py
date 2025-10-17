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
    app.config.update(WTF_CSRF_ENABLED=False)
    with app.app_context():
        db.create_all()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()
    

@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def admin_user(app):
    from extensions import db
    from models import User, Role

    password = "Password123!"
    with app.app_context():
        role = db.session.query(Role).filter_by(name="Beheerder").first()
        if not role:
            role = Role(name="Beheerder")
            db.session.add(role)
            db.session.commit()
        existing = db.session.query(User).filter_by(username="test_admin").first()
        if existing:
            user = existing
        else:
            user = User(
                first_name="Test",
                last_name="Admin",
                username="test_admin",
                email="test_admin@example.com",
                is_active=True,
            )
            user.set_password(password)
            user.roles.append(role)
            db.session.add(user)
            db.session.commit()
        db.session.expunge_all()
    return {"username": "test_admin", "password": password}


@pytest.fixture()
def auth_client(client, admin_user):
    response = client.post(
        "/auth/login",
        data={"username": admin_user["username"], "password": admin_user["password"]},
        follow_redirects=True,
    )
    assert response.status_code == 200
    return client
