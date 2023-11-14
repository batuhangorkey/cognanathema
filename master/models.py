import secrets
from datetime import datetime, timedelta
from enum import Enum, unique
from os import name

import humanize
from flask import request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, ForeignKey, Integer, String, func
from sqlalchemy.ext.hybrid import hybrid_method
from sqlalchemy.orm import relationship
from werkzeug.security import check_password_hash, generate_password_hash

from master.app import db


class JobTypeEnum(Enum):
    OPERATOR = "operator"
    SLAVE = "slave"


class User(db.Model):
    id = Column(db.Integer(), primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    mail = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(64), nullable=False)

    roles = db.relationship(
        "Role", secondary="roles_users", backref=db.backref("users", lazy="dynamic")
    )
    identity = db.relationship("Identity", backref=db.backref("user", lazy=True))

    def __init__(self, username, mail, password) -> None:
        self.username = username
        self.mail = mail
        self.password = generate_password_hash(password)

    def __repr__(self):
        return f"User('{self.username}', '{self.mail}')"

    def is_active(self):
        return True

    def get_id(self):
        return str(self.id)

    def is_authenticated(self):
        password = request.form.get("password")
        if password is None:
            return False
        return self.check_password(password)

    def set_password(self, password: str):
        if password is None:
            raise NotImplementedError
        self.password = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        if password is None:
            return False
        return check_password_hash(self.password, password)


class RolesUsers(db.Model):
    id = Column(Integer(), primary_key=True)
    user_id = Column(Integer(), ForeignKey("user.id"))
    role_id = Column(Integer(), ForeignKey("role.id"))


class Role(db.Model):
    id = Column(Integer(), primary_key=True)
    name = Column(String(80), unique=True)
    description = Column(String(255))


class Detection(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())
    filepath = db.Column(db.String(255), nullable=False)

    identity_id = db.Column(db.Integer, db.ForeignKey("identity.id"), nullable=True)
    identity = db.relationship("Identity", backref=db.backref("detections", lazy=True))

    def __repr__(self):
        identity_name = self.get_identity()
        return f"Detections(ID: '{identity_name}', '{self.timestamp}')"

    def get_identity(self) -> str:
        if self.identity_id:
            identity_name = Identity.query.get_or_404(self.identity_id).name
        else:
            identity_name = "Unknown"
        return identity_name

    def serialize(self):
        return {
            "id": self.id,
            "name": self.get_identity(),
            "timestamp": self.timestamp.ctime(),
            "time_human": self.get_timestamp(),
            "filepath": self.filepath,
        }

    def get_timestamp(self):
        current_datetime = datetime.utcnow()
        time_difference = (current_datetime - self.timestamp).total_seconds()
        formatted_time = humanize.naturaltime(time_difference)
        return formatted_time

    @hybrid_method
    def get_recent_detections(self):
        one_day_ago = datetime.utcnow() - timedelta(days=1)
        detections = self.query.filter(Detection.timestamp >= one_day_ago)
        detections = detections.order_by(Detection.timestamp.desc())
        return detections


class Identity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    data = db.Column(db.JSON, nullable=True)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, unique=True)

    def __init__(self, name, data) -> None:
        super().__init__()
        self.name = name
        self.data = data

    def __repr__(self):
        return f"Identity('{self.name}', '{self.data}')"


class AuthKey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    auth_key = db.Column(db.String(64), unique=True, nullable=False)
    created_at = db.Column(
        db.DateTime, default=db.func.current_timestamp(), nullable=False
    )
    type = db.Column(db.Enum(JobTypeEnum), nullable=False)
    used = db.Column(db.Boolean, default=False, nullable=False)

    def __init__(self, key: str, type: JobTypeEnum) -> None:
        self.set_authkey(key)
        self.type = type

    def __repr__(self) -> str:
        return f"AuthKey {self.id}: {self.auth_key}"

    def set_authkey(self, authkey: str) -> None:
        self.auth_key = generate_password_hash(authkey)

    def check_authkey(self, authkey: str) -> bool:
        return check_password_hash(self.auth_key, authkey)


def generate_authkey(type: JobTypeEnum):
    if type == JobTypeEnum.OPERATOR:
        authkey = secrets.token_urlsafe(4)
    elif type == JobTypeEnum.SLAVE:
        authkey = secrets.token_urlsafe(16)
    else:
        raise NotImplementedError
    return authkey


def check_authkey(sus_key) -> bool:
    one_week_ago = datetime.utcnow() - timedelta(weeks=1)
    keys = AuthKey.query.filter(
        AuthKey.used == False, AuthKey.created_at >= one_week_ago
    ).all()  # type: ignore
    for key in keys:
        if key.check_authkey(sus_key):
            key.used = True
            db.session.commit()
            return True
    return False
