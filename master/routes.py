from io import BytesIO
import os
import secrets
from datetime import datetime, timedelta
import socket
from typing import List

import flask
import humanize
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
from PIL import Image
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage

from flask_sqlalchemy.query import Query
import magic

from .app import app, db, recognizer, socketio
from .models import Detection, Identity, User, check_authkey
import logging

logger = logging.getLogger("my_logger")


@socketio.on("connect")
def handle_connect():
    logger.info("Socketio client connected!")


@app.before_request
def before_request():
    # logger.info("Host: %s" % request.host)
    # logger.info("User agent: %s" % request.headers.get("User-agent"))
    # logger.info("Root url: %s" % request.url_root)
    # logger.info("Base url: %s" % request.base_url)
    pass


@app.route("/")
def index():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    user_id = session.get("user_id")
    user: User = User.query.get_or_404(user_id)

    detections = Detection.get_recent_detections()

    if request.args.get("v") == "t":
        session["view_mode"] = "table"
    if request.args.get("v") == "s":
        session["view_mode"] = "special"

    if session.get("view_mode", "table") == "table":
        return render_template("index.html", user=user, detections=detections)
    else:
        return render_template("mosaic.html", user=user, detections=detections)


@app.route("/inspect/<id>", methods=["GET", "POST"])
def inspect(id):
    # print(request.url.replace("http", "https"))

    user_id = session.get("user_id")
    if not user_id or not session.get("logged_in"):
        return redirect(url_for("login"))

    det: Detection = Detection.query.get_or_404(id)

    print(det.identity)
    # print(det.identity.name)
    user = User.query.get(user_id)

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

    return render_template("inspect.html", user=user, det=det)


@app.route("/profile", methods=["GET", "POST"])
def profile():
    user_id = session.get("user_id")
    if not user_id or not session.get("logged_in"):
        return redirect(url_for("index"))

    if request.method == "POST":
        user = User.query.get_or_404(user_id)
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

    user: User = User.query.get_or_404(user_id)
    return render_template("profile.html", user=user)


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("logged_in"):
        return redirect(url_for("index"))
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = User.query.filter(User.username == username).first()
        if user is None:
            return render_template("login.html", context={"ERROR": "USER_NOT_FOUND"})
        if user.check_password(password):
            session["logged_in"] = True
            session["user_id"] = user.id
            return redirect(url_for("index"))
        else:
            return render_template("login.html", context={"ERROR": "PASSWORD"})
    return render_template("login.html")


@app.route("/logout")
def logout():
    if session.get("user_id"):
        session.pop("user_id")
    session["logged_in"] = False
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
            return render_template("signup.html", context={"ERROR": "USER_EXISTS"})
        p = request.form.get("password")
        k = request.form.get("authkey")
        new_user = User(username, mail, p)
        if check_authkey(k):
            db.session.add(new_user)
            db.session.commit()
            return render_template("signup.html", context={"ERROR": "SUCCESS"})
        else:
            return render_template(
                "signup.html", context={"ERROR": "AUTHKEY_NOT_FOUND"}
            )

    return render_template("signup.html")


@app.route("/upload/<path:filename>", methods=["GET"])
def view_upload(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route("/upload", methods=["POST"])
def upload():
    # TODO: ORDER AND GROUP THE SAME PEOPLE,
    # OTHERWISE MAIN PAGE IS FILLED WITH THE SAME HUMAN
    # TODO: MOVE THIS TO SOMEWHERE ELSE AND REWRITE, THIS CODE IS UGLY
    print(request.remote_addr)

    uploaded_file = request.files.get("file")
    timestamp = request.form.get("timestamp")
    face_detection_time = request.form.get("face_detection_time")

    if not uploaded_file:
        return jsonify("Missing file"), 400
    if not allowed_file(uploaded_file.filename):
        return jsonify("File type is not correct"), 400
    # if not allowed_file_size(uploaded_file.filename):
    #     return jsonify("File size is too big"), 400
    if not timestamp:
        return jsonify("Missing timestamp"), 400
    if not face_detection_time and not isinstance(face_detection_time, int):
        return jsonify("Error on face detection time"), 400
    else:
        face_detection_time = int(face_detection_time)
    try:
        timestamp = datetime.strptime(timestamp, "%a %b %d %H:%M:%S %Y")
    except ValueError:
        return jsonify("Timestamp not in correct format"), 400

    server_delay = elapsed_time(timestamp)

    sanitize_file(uploaded_file)

    filename = secrets.token_urlsafe(32) + ".jpg"
    path = os.path.join(app.root_path, "uploads", filename)

    try:
        uploaded_file.save(path)
        PIL_img = Image.open(path).convert("L")
    except Exception as e:
        print(e)
        if os.path.exists(path):
            print(f"Removed {path}")
            os.remove(path)
        return jsonify(f"Error: {e}"), 400

    img_numpy = np.array(PIL_img, "uint8")
    id, confidence = recognizer.predict(img_numpy)
    print(id, confidence)

    face_recognition = elapsed_time(timestamp) - server_delay

    new_det = Detection(timestamp=timestamp, filepath=filename)  # type: ignore

    if confidence > 70:
        # TODO: IDEA: weak identites
        identity = Identity.query.get_or_404(id)
        print(f"Weak identity: {identity}")
    else:
        # Identity found
        # see if we detected this human in the last one minute
        identity = Identity.query.get_or_404(id)
        min_ago = datetime.utcnow() - timedelta(minutes=1)
        past_detections = Detection.query.filter(
            Detection.timestamp >= min_ago, Detection.identity == identity
        )
        if past_detections.count() > 0:
            return jsonify("repetitive spam"), 400

        logger.info(f"Found identity: {identity}")
        new_det.identity_id = identity.id

    db.session.add(new_det)
    db.session.commit()

    data = new_det.serialize()

    # print(f"From node to end of recognition in us: {elapsed_time(timestamp)}")
    # h = humanize.naturaldelta(elapsed, minimum_unit="milliseconds")
    # print(h)

    performance = {
        "server_delay": server_delay.microseconds // 1000,
        "face_detection_time": face_detection_time // 1000,
        "face_recognition": face_recognition.microseconds // 1000,
    }

    logger.info(performance)

    socketio.emit("update_table", data)

    return jsonify(data), 200


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
    return render_template("live.html", user=None)


@app.route("/log", methods=["GET"])
def log():
    # TODO: IMPLEMENT A LIVE LOG PAGE
    return Response()


def allowed_file(file) -> bool:
    # DEPRECATED
    k = "." in file
    if not k:
        return False
    return file.rsplit(".", 1)[1].lower() == "jpg"


def check_login(func):
    user_id = session.get("user_id")
    if not user_id or not session.get("logged_in"):
        return redirect(url_for("index"))
    user = User.query.get(user_id)
    return user


def trigger_update_table():
    # TODO: This method does nothing
    # socketio.emit("update_table", data)
    pass


def elapsed_time(time: datetime) -> timedelta:
    time_finished = datetime.utcnow() - time
    elapsed = timedelta(seconds=time_finished.total_seconds())
    return elapsed


def sanitize_file(file: FileStorage):
    mime = magic.from_buffer(file.stream.read(2048), mime=True)
    print(mime)
    file.stream.seek(0)
    if mime.startswith("image"):
        return True
    return False
