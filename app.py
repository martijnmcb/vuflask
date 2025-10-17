import os
from flask import Flask, redirect, url_for, request, abort
from config import Config
from extensions import db, login_manager, migrate
from models import User, Role
from blueprints.auth.routes import bp as auth_bp
from blueprints.main.routes import bp as main_bp
from blueprints.admin.routes import bp as admin_bp
from blueprints.lecturer import bp as lecturer_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    login_manager.login_view = "auth.login"

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(lecturer_bp)

    @app.route("/init")
    def init():
        # Guard: only allow in debug or with INIT_TOKEN
        if not app.debug:
            token = request.args.get("token")
            if not token or token != os.getenv("INIT_TOKEN"):
                abort(403)
        # Ensure tables exist before seeding default data (useful for fresh SQLite setups)
        db.create_all()
        # maak basisrollen
        for r in ["Beheerder", "Gebruiker", "Lezer"]:
            if not db.session.query(Role).filter_by(name=r).first():
                db.session.add(Role(name=r))
        db.session.commit()
        # maak admin user als die nog niet bestaat
        if not db.session.query(User).filter_by(username="admin").first():
            u = User(
                first_name="Admin",
                last_name="User",
                username="admin",
                email="admin@example.com",
                is_active=True,
            )
            seed_password = os.getenv("ADMIN_SEED_PASSWORD", "admin123")
            try:
                u.set_password(seed_password)
            except ValueError as exc:
                return str(exc), 500
            admin_role = db.session.query(Role).filter_by(name="Beheerder").first()
            u.roles.append(admin_role)
            db.session.add(u)
            db.session.commit()
        return redirect(url_for("auth.login"))

    return app

if __name__ == "__main__":
    app = create_app()
    debug = os.getenv("FLASK_DEBUG") == "1"
    app.run(host="0.0.0.0", port=5000, debug=debug)
