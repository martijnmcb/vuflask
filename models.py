from datetime import datetime
from passlib.hash import pbkdf2_sha256
from flask_login import UserMixin
from extensions import db

# Tabel associatie User <-> Role (many-to-many)
user_roles = db.Table(
    "user_roles",
    db.Column("user_id", db.Integer, db.ForeignKey("users.id")),
    db.Column("role_id", db.Integer, db.ForeignKey("roles.id")),
)

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(120), nullable=False)
    last_name  = db.Column(db.String(120), nullable=False)
    email      = db.Column(db.String(255), unique=True, index=True)
    phone      = db.Column(db.String(50))
    username   = db.Column(db.String(120), unique=True, index=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active  = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    roles = db.relationship("Role", secondary=user_roles, back_populates="users")
    project_links = db.relationship(
        "UserProject",
        cascade="all, delete-orphan",
        back_populates="user",
    )

    def set_password(self, raw):
        if raw is None:
            raise ValueError("Wachtwoord ontbreekt")
        try:
            raw.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ValueError("Ongeldig wachtwoord") from exc
        self.password_hash = pbkdf2_sha256.hash(raw)

    def check_password(self, raw):
        if raw is None:
            return False
        try:
            raw.encode("utf-8")
        except UnicodeEncodeError:
            return False
        try:
            return pbkdf2_sha256.verify(raw, self.password_hash)
        except ValueError:
            return False

    @property
    def project_names(self):
        return [link.project for link in self.project_links]

class Role(db.Model):
    __tablename__ = "roles"
    id   = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)  # Beheerder, Gebruiker, Lezer
    users = db.relationship("User", secondary=user_roles, back_populates="roles")


class UserProject(db.Model):
    __tablename__ = "user_projects"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    project = db.Column(db.String(120), nullable=False)

    user = db.relationship("User", back_populates="project_links")

    __table_args__ = (
        db.UniqueConstraint("user_id", "project", name="uq_user_project_membership"),
    )

# Opslag van SQL Server connectieparameters (via UI te beheren)
class ConnectionSetting(db.Model):
    __tablename__ = "connection_settings"
    id       = db.Column(db.Integer, primary_key=True)
    host     = db.Column(db.String(255), default="127.0.0.1")
    port     = db.Column(db.Integer, default=1433)
    database = db.Column(db.String(255), nullable=False, default="master")
    username = db.Column(db.String(255), nullable=False, default="sa")
    password = db.Column(db.String(255), nullable=False, default="")
    odbc_driver = db.Column(db.String(255), nullable=False, default="ODBC Driver 18 for SQL Server")
    trust_server_cert = db.Column(db.Boolean, default=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def build_uri(self):
        trust = "yes" if self.trust_server_cert else "no"
        # SQLAlchemy URI via pyodbc
        return (f"mssql+pyodbc://{self.username}:{self.password}"
                f"@{self.host}:{self.port}/{self.database}"
                f"?driver={self.odbc_driver.replace(' ', '+')}"
                f"&TrustServerCertificate={trust}")

class ConnectionProfile(db.Model):
    __tablename__ = "connection_profiles"
    id       = db.Column(db.Integer, primary_key=True)
    name     = db.Column(db.String(120), nullable=False, default="Default")
    project  = db.Column(db.String(120), nullable=False, default="Algemeen")
    host     = db.Column(db.String(255), default="127.0.0.1")
    port     = db.Column(db.Integer, default=1433)
    database = db.Column(db.String(255), nullable=False, default="master")
    username = db.Column(db.String(255), nullable=False, default="sa")
    password = db.Column(db.String(255), nullable=False, default="")
    odbc_driver = db.Column(db.String(255), nullable=False, default="ODBC Driver 17 for SQL Server")
    trust_server_cert = db.Column(db.Boolean, default=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def build_uri(self):
        trust = "yes" if self.trust_server_cert else "no"
        return (
            f"mssql+pyodbc://{self.username}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
            f"?driver={self.odbc_driver.replace(' ', '+')}"
            f"&TrustServerCertificate={trust}"
        )
