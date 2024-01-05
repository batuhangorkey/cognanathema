import logging
import os
import secrets
from datetime import datetime, timedelta
from enum import Enum, unique
from os import name

import humanize
from flask import request
from flask_sqlalchemy import SQLAlchemy
from PIL import Image
import numpy as np
from sqlalchemy import Column, ForeignKey, Integer, String, func
from sqlalchemy.ext.hybrid import hybrid_method
from sqlalchemy.orm import relationship
from sqlalchemy.orm.attributes import flag_modified
from werkzeug.security import check_password_hash, generate_password_hash
from master import cognaface

from master.app import app, db

logger = logging.getLogger("my_logger")


class JobTypeEnum(Enum):
    OPERATOR = "operator"
    SLAVE = "slave"


class User(db.Model):
    id = Column(db.Integer(), primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    mail = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(64), nullable=False)

    roles = db.relationship(
        "Role",
        secondary="roles_users",
        backref=db.backref("users", lazy="dynamic"),
    )

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
    thermal_path = db.Column(db.String(255), nullable=True)
    # filename = db.Column(db.String(255), nullable=True)
    data = db.Column(db.JSON, nullable=True)

    identity_id = db.Column(
        db.Integer, db.ForeignKey("identity.id"), nullable=True
    )
    identity = db.relationship(
        "Identity", backref=db.backref("detections", lazy=True)
    )

    def __repr__(self):
        identity_name = self.get_identity()
        return f"Detections(ID: '{identity_name}', '{self.timestamp}')"

    @property
    def face_path(self):
        base = os.path.basename(self.filepath)
        path = os.path.join("face", base)
        return path

    @property
    def _thermal_path(self):
        base = os.path.basename(self.filepath)
        path = os.path.join("thermal", base)
        return path

    @property
    def mean_temp(self):
        if self.data is None:
            return None
        if self.data.get("temps"):
            if self.data.get("temps").get("mean_temp"):
                return "%.2f" % float(self.data.get("temps").get("mean_temp"))
            if self.data.get("temps").get("face_mean"):
                return "%.2f" % float(self.data.get("temps").get("face_mean"))
        return None

    @property
    def scene_mean_temp(self):
        if self.data is None:
            return None
        if self.data.get("temps") and self.data.get("temps").get("scene_mean"):
            return "%.2f" % float(self.data.get("temps").get("scene_mean"))
        return None

    @property
    def cosine_distance(self):
        if self.data.get("face_vector") is None:
            image = Image.open(
                os.path.join(app.config["UPLOAD_FOLDER"], self.filepath)
            )
            vec = cognaface.get_face_vector(image).tolist()
            self.data["face_vector"] = vec
            # what the fuck is this
            # we force the alchemy to commit updates..
            flag_modified(self, "data")
            db.session.commit()
        else:
            vec = self.data.get("face_vector")
        sims = cognaface.compute_similarity(vec)
        i = np.argmin(sims)
        return Identity.query.get(int(cognaface.ID_ARRAY[i])).name

    @property
    def euclidean_distance(self):
        if self.data.get("face_vector") is None:
            image = Image.open(
                os.path.join(app.config["UPLOAD_FOLDER"], self.filepath)
            )
            vec = cognaface.get_face_vector(image).tolist()
            self.data["face_vector"] = vec
            # what the fuck is this
            # we force the alchemy to commit updates..
            flag_modified(self, "data")
            db.session.commit()
        else:
            vec = self.data.get("face_vector")
        sims = cognaface.compute_euclidean(vec)
        i = np.argmin(sims)

        return Identity.query.get(int(cognaface.ID_ARRAY[i])).name

    def is_fake(self):
        if (
            self.data
            and self.data.get("temps")
            and self.data.get("temps").get("face_mean")
        ):
            temp_check = float(
                self.data.get("temps").get("scene_mean")
            ) * 1.1 < float(self.data.get("temps").get("face_mean"))

            if temp_check:
                return "Human"
        return "Fake"

    def get_identity(self) -> str:
        if self.identity_id is None:
            return "Unknown"
        if isinstance(self.identity_id, bytes):
            # backwards compat
            id = int.from_bytes(self.identity_id, byteorder="little")
            identity = Identity.query.get(id)
        else:
            identity = Identity.query.get(self.identity_id)
        if identity:
            identity_name = identity.name
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
            "fake": self.is_fake(),
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

    def __init__(self, name, data) -> None:
        super().__init__()
        self.name = name
        self.data = data

    def __repr__(self):
        return f"Identity('{self.name}', '{self.data}')"

    def get_face(self):
        if self.data is None:
            return "holder.js/300x300"
        path = self.data.get("face_path")
        if path is None:
            return "holder.js/300x300"
        pre = os.path.join(app.root_path, "uploads")
        path = path.removeprefix(pre)
        path = "upload" + path
        return path


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
