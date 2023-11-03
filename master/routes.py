import logging
import os
import secrets
import socket
from datetime import datetime, timedelta
from io import BytesIO
from typing import List

import flask
import humanize
import magic
import numpy as np
import requests
from flask import (
    Response,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user
from flask_sqlalchemy.query import Query
from PIL import Image
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from master.app import app, db, socketio
from master.extensions import login_manager
from master.models import Detection, Identity, User, check_authkey

logger = logging.getLogger("my_logger")

# @login_manager.unauthorized
# def unauthorized():
#    pass


@socketio.on("connect")
def handle_connect():
    client_id = request.sid  # type: ignore
    logger.info("Socketio client connected with ID: %s" % client_id)


@socketio.on("disconnect")
def handle_disconnect():
    client_id = request.sid  # type: ignore
    socketio.emit("stop_stream")
    logger.info("Socketio client disconnected with ID: %s" % client_id)


@app.before_request
def before_request():
    # logger.info("Host: %s" % request.host)
    # logger.info("User agent: %s" % request.headers.get("User-agent"))
    # logger.info("Root url: %s" % request.url_root)
    # logger.info("Base url: %s" % request.base_url)
    pass


@app.route("/")
@login_required
def index():
    detections = Detection.get_recent_detections()

    if request.args.get("v") == "t":
        session["view_mode"] = "table"
    if request.args.get("v") == "s":
        session["view_mode"] = "special"

    if session.get("view_mode", "table") == "table":
        return render_template("index.html", detections=detections)
    else:
        return render_template("mosaic.html", detections=detections)


@app.route("/inspect/<id>", methods=["GET", "POST"])
@login_required
def inspect(id):
    user: User = current_user

    det: Detection = Detection.query.get_or_404(id)

    logger.info(det.identity)

    if request.method == "POST":
        name = request.form.get("name")
        if not name:
            return redirect(url_for("inspect", id=id))
        name = name.strip()
        c = Identity.query.filter(Identity.name == name).first()
        if c:
            # entered name is a registered identity
            det.identity = c
            db.session.commit()
            return redirect(url_for("inspect", id=id))
        else:
            # add the new identity
            new_identity = Identity(name=name)  # type: ignore
            db.session.add(new_identity)
        if det.identity:
            if name == "":
                # delete the identity connected to this detection
                det.identity_id = None
        else:
            # connect new identity and detection together
            det.identity_id = new_identity.id
        db.session.commit()
        return redirect(url_for("inspect", id=id))

    return render_template("inspect.html", det=det)


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user: User = current_user

    if request.method == "POST":
        oldpassword = request.form.get("password")
        username = request.form.get("username")
        newpassword = request.form.get("newPassword")
        mail = request.form.get("mail")
        if (
            username is None
            or mail is None
            or oldpassword is None
            or newpassword is None
        ):
            return redirect(url_for("profile", user=user))

        username = username.strip()
        mail = mail.strip()

        if oldpassword is None or not user.check_password(oldpassword):
            return render_template(
                "profile.html", user=user, context={"ERROR": "PASSWORD_INCORRECT"}
            )

        user_e = None
        if username != user.username:
            user_e = User.query.filter(User.username == username).first()
        if mail != user.mail:
            user_e = User.query.filter(User.mail == mail).first()
        if user_e:
            return render_template(
                "profile.html", user=user, context={"ERROR": "USER_EXISTS"}
            )
        user.username = username
        user.mail = mail

        user.set_password(newpassword)
        db.session.commit()
        return render_template("profile.html", user=user, context={"ERROR": "SUCCESS"})

    return render_template("user/profile.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        user = User.query.filter(User.username == username).first()
        if user is None:
            return render_template(
                "user/login.html", context={"ERROR": "USER_NOT_FOUND"}
            )
        res = login_user(user)
        if res:
            return redirect(url_for("index"))
        else:
            return render_template("user/login.html", context={"ERROR": "PASSWORD"})
    return render_template("user/login.html")


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("index"))


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        mail = request.form.get("mail")
        username = request.form.get("username")

        if not mail or not username:
            return redirect(url_for("signup"))

        mail = mail.strip()
        username = username.strip()

        user = User.query.filter(User.mail == mail).first()
        if user:
            return render_template("user/signup.html", context={"ERROR": "USER_EXISTS"})
        p = request.form.get("password")
        k = request.form.get("authkey")
        new_user = User(username, mail, p)
        if check_authkey(k):
            db.session.add(new_user)
            db.session.commit()
            return render_template("user/signup.html", context={"ERROR": "SUCCESS"})
        else:
            return render_template(
                "user/signup.html", context={"ERROR": "AUTHKEY_NOT_FOUND"}
            )

    return render_template("user/signup.html")


@app.route("/upload/<path:filename>", methods=["GET"])
def view_upload(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route("/identity/<id>", methods=["GET"])
def identity(id):
    detections = Detection.query.filter(Detection.identity_id == id)

    return render_template("identity.html", user=None, detections=detections)


@app.route("/identities", methods=["GET"])
def identities():
    # TODO:
    identities = Identity.query.all()

    return render_template("identity.html", identities=identities, user=None)


@app.route("/live", methods=["GET"])
def live():
    # learn webrtc, this is still not implemented
    
    return render_template("live.html")


@app.route("/log", methods=["GET"])
def log():
    # TODO: IMPLEMENT A LIVE LOG PAGE
    return Response()


def trigger_update_table():
    # TODO: This method does nothing
    # socketio.emit("update_table", data)
    pass
