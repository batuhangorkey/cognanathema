import base64
import os
import secrets
from datetime import datetime, timedelta
from functools import wraps
from io import BytesIO
from shlex import join
from time import time
from typing import List

import magic
import numpy as np
from flask import Blueprint, abort, current_app, jsonify, request, session
from flask_login import current_user, logout_user
from flask_socketio import SocketIO, join_room, rooms, send
from flask_sqlalchemy.query import Query
from PIL import Image
from sqlalchemy.orm.attributes import flag_modified
from werkzeug.datastructures import FileStorage

from master.api import api
from master.app import app, cognaface, db, logger
from master.cognaface import draw_face, get_face
from master.extensions import socketio
from master.models import Detection, Identity, User

MAX_FILE_SIZE = 16 * 1e3


def check_json(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        data = request.json
        if not data:
            return jsonify("JSON missing"), 400
        return func(*args, **kwargs)

    return wrapper


def check_image_file(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        data = request.json
        if not data:
            return jsonify("JSON missing"), 400
        return func(*args, **kwargs)

    return wrapper


def check_image_json(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        data = request.json
        if not data:
            return jsonify("JSON missing"), 400
        return func(*args, **kwargs)

    return wrapper


def check_id(func):
    @wraps(func)
    def wrapper():
        data = request.json
        if not data:
            return jsonify("JSON missing"), 400

        id = data.get("id")
        if not id or id == "":
            return jsonify("ID missing"), 400
        return func()

    return wrapper


def check_sent_image(func):
    @wraps(func)
    def wrapper():
        data = request.json
        if not data:
            return jsonify("JSON missing"), 400
        id = data.get("id")
        if not id or id == "":
            return jsonify("ID missing"), 400
        return func()

    return wrapper


@socketio.on("connect")
def handle_connect():
    client_id = request.sid  # type: ignore
    logger.info("Socketio client connected with ID: %s" % client_id)


@socketio.on("disconnect", namespace="/live")
def handle_disconnect():
    client_id = request.sid  # type: ignore
    socketio.emit("stop_stream", {"client": client_id})
    logger.info("Socketio client disconnected with ID: %s" % client_id)
    logger.info("Socketio client rooms: %s" % rooms())


@socketio.on("message")
def handle_message(data):
    logger.info(data)

    if data.get("job") == "slave":
        logger.info("Joined room")
        join_room("streamer_room")

    if data.get("viewer_count"):
        # count = data.get("viewer_count")
        socketio.send(data, to="viewer_room", namespace="/live")

    if data.get("stream") == "start":
        socketio.send("streaming", to="viewer_room", namespace="/live")


@socketio.on("video_data")
def handle_video_data(data):
    image_data = data["image_data"]

    image_bytes = base64.b64decode(image_data.split(",")[1])

    stream = BytesIO(image_bytes)
    image = Image.open(stream)
    image = draw_face(image)
    stream.seek(0)
    stream.truncate(0)
    image.save(stream, "jpeg")
    transformed_image = encode_image(stream.getvalue())

    socketio.emit(
        "transformed_image", {"transformed_image": transformed_image}
    )


@socketio.on("stream")
def handle_stream():
    logger.info(
        "Starting a live stream requested by client id: %s" % request.sid
    )

    # socketio.emit("start_stream", {"client": request.sid})


@socketio.on("join_stream", namespace="/live")
def handle_start_stream():
    # TODO: ADD TOKEN VERIFICATION, ITS IMPORTANTTT!!
    logger.info(
        "Starting a live stream requested by client id: %s" % request.sid
    )
    join_room("viewer_room", namespace="/live")

    socketio.send("Looking for streamer", to=request.sid)

    socketio.emit("start_stream", {"client": request.sid}, to="streamer_room")


@socketio.on("live_stream")
def handle_live_stream(data):
    encoded_frame = encode_image(data["frame"])
    data["frame"] = encoded_frame

    if data["type"] == "thermal":
        event = "receive_thermal_frame"
    else:
        event = "receive_cam_frame"

    socketio.emit(event, data, to="viewer_room", namespace="/live")


@api.route("/detection", methods=["POST", "DELETE"])
def detection():
    if request.json is None:
        return jsonify("Error"), 400
    id = request.json["id"]
    det: Detection = Detection.query.get_or_404(id)
    if request.method == "DELETE":
        det.face_path
        db.session.delete(det)
        db.session.commit()
        return jsonify("Successfully deleted"), 200

    return jsonify("Error"), 400


@api.route("/detection/mark", methods=["POST"])
def detection_mark():
    if request.json is None:
        return jsonify("Error"), 400
    logger.info(request.json)
    id = request.json["id"]

    det: Detection = Detection.query.get_or_404(id)

    if request.method == "POST":
        if request.json["type"] == "face":
            det.data["face_mark"] = request.json["mark"]
        if request.json["type"] == "temp":
            det.data["temp_mark"] = request.json["mark"]

        flag_modified(det, "data")
        db.session.commit()
        return jsonify("Success"), 200

    return jsonify("Error"), 400


@check_id
@api.route("/identity", methods=["POST", "DELETE"])
def identity():
    id = request.json["id"]
    if request.method == "POST":
        det: Detection = Detection.query.get_or_404(id)
        det.identity_id = None
        db.session.commit()
    if request.method == "DELETE":
        pass
    return jsonify("Successfully deleted"), 200


@api.route("/latest_data", methods=["GET"])
def latest_data():
    one_day_ago = datetime.utcnow() - timedelta(days=1)
    detections_q: Query = Detection.query.filter(
        Detection.timestamp >= one_day_ago
    )
    detections: List[Detection] = detections_q.order_by(
        Detection.timestamp.desc()
    ).all()

    data = [det.serialize() for det in detections]
    return jsonify(data)


@check_json
@api.route("/upload/picture", methods=["POST"])
def upload_picture():
    # A picture sent, detected face returned
    data = request.json
    image_data: str = data.get("image")

    image_bytes = base64.b64decode(image_data.split(",")[1])
    if not sanitize_file(image_bytes):
        return jsonify("File not safe"), 400

    stream = BytesIO(image_bytes)
    image = Image.open(stream)
    face = get_face(image)
    if face is None:
        return jsonify({"error": "Face not found"}), 400
    logger.info("Face found")
    stream.seek(0)
    stream.truncate(0)
    face.save(stream, "jpeg")
    face_binary_data = stream.getvalue()
    face_base64 = base64.b64encode(face_binary_data).decode("utf-8")
    # this part is missing, i dont know why
    # it is important for the website to understand its format
    face_base64 = "data:image/jpeg;base64," + face_base64

    return jsonify({"face": face_base64}), 200


@check_json
@api.route("/detect/face", methods=["POST"])
def detect_face():
    logger.info(request.form)
    uploaded_file = request.files.get("photo")

    if not sanitize_file(uploaded_file):
        return jsonify("File not safe"), 200

    stream = BytesIO()
    uploaded_file.save(stream)

    image = Image.open(stream)
    face = get_face(image)

    if face is None:
        return jsonify({"error": "Face not found"}), 200

    logger.info("Face found")

    stream.seek(0)
    stream.truncate(0)

    face.save(stream, "jpeg")
    face_binary_data = stream.getvalue()
    face_base64 = base64.b64encode(face_binary_data).decode("utf-8")
    # this part is missing, i dont know why
    # it is important for the website to understand its format
    face_base64 = "data:image/jpeg;base64," + face_base64
    data = {"face": face_base64}

    return jsonify({"result": data}), 200


@check_json
@api.route("/register/face", methods=["POST"])
def register_face():
    image_data: str = request.json.get("image")
    # data comes with a leading part, it tells the type
    image_bytes = base64.b64decode(image_data.split(",")[1])

    name: str = request.json.get("name")

    if not sanitize_file(image_bytes):
        return jsonify("File not safe"), 400

    stream = BytesIO(image_bytes)
    image = Image.open(stream)

    filename = secrets.token_urlsafe(4) + ".jpg"
    path = os.path.join(app.config["UPLOAD_FOLDER"], "face", filename)
    image.save(path)

    vector = cognaface.get_face_vector(image).tolist()

    data = {"face_vector": vector, "face_path": path}

    identity = Identity.query.filter(Identity.name == name).first()
    if identity:
        identity.data = data
    else:
        new = Identity(name=name, data=data)
        db.session.add(new)
    db.session.commit()
    return jsonify({"result": "success"}), 200


@api.route("/recognize", methods=["POST"])
def recognize():
    # TODO: ORDER AND GROUP THE SAME PEOPLE,
    # OTHERWISE MAIN PAGE IS FILLED WITH THE SAME HUMAN
    # TODO: MOVE THIS TO SOMEWHERE ELSE AND REWRITE, THIS CODE IS UGLY
    logger.info("Remote address: %s" % request.remote_addr)

    uploaded_file = request.files.get("face_file")
    thermal = request.files.get("thermal_file")
    if not uploaded_file or not thermal:
        return jsonify("Missing file"), 400
    timestamp = request.form.get("timestamp")
    temps = {
        "face_mean": request.form.get("face_mean"),
        "scene_max": request.form.get("scene_max"),
        "scene_min": request.form.get("scene_min"),
        "scene_mean": request.form.get("scene_mean"),
    }

    if not sanitize_file(uploaded_file) or not sanitize_file(thermal):
        return jsonify("File is not safe"), 400

    try:
        timestamp = datetime.strptime(timestamp, "%a %b %d %H:%M:%S %Y")
    except ValueError:
        return jsonify("Timestamp not in correct format"), 400

    stream = BytesIO()
    uploaded_file.save(stream)
    image = Image.open(stream)

    filename = secrets.token_urlsafe(4) + ".jpg"

    face_filepath = os.path.join("face", filename)
    thermal_filepath = os.path.join("thermal", filename)

    face_fullpath = os.path.join(app.config["UPLOAD_FOLDER"], face_filepath)
    thermal_fullpath = os.path.join(
        app.config["UPLOAD_FOLDER"], thermal_filepath
    )

    vector1 = cognaface.get_face_vector(image)
    found_id = cognaface.find_identity(vector1)

    logger.info(temps)
    logger.info(found_id)

    new_det = Detection(timestamp=timestamp, filepath=face_filepath)  # type: ignore
    new_det.data = {
        "temps": temps,
        "fake": False,
        "face_vector": vector1.tolist(),
    }
    new_det.thermal_path = thermal_filepath

    if found_id is None:
        response_data = {"identity": "not found"}
    else:
        logger.info("Finding ID with: %d" % found_id)
        found_identity = Identity.query.get(found_id)
        logger.info(found_identity.name)

        new_det.identity_id = found_id

        response_data = {"identity": found_identity.name}

    db.session.add(new_det)
    try:
        image.save(face_fullpath)
        thermal.save(thermal_fullpath)
    except Exception:
        db.session.rollback()
    else:
        db.session.commit()

    data = new_det.serialize()
    socketio.emit("update_table", data)

    return jsonify(response_data), 200


def sanitize_file(file):
    # check for file anomalities
    logger.info("Type of file: %s" % type(file))
    if isinstance(file, bytes):
        file_size = len(file)
        logger.info("File length: %s kb" % (file_size / 1000))
        mime = magic.from_buffer(file, mime=True)
    elif isinstance(file, FileStorage):
        mime = magic.from_buffer(file.stream.read(2048), mime=True)
        file.stream.seek(0)
    elif file is None:
        return False
    else:
        raise NotImplementedError()
    logger.info("Mime type: %s" % mime)
    if mime.startswith("image"):
        return True
    return False


def elapsed_time(time: datetime) -> timedelta:
    time_finished = datetime.utcnow() - time
    elapsed = timedelta(seconds=time_finished.total_seconds())
    return elapsed


def decode_image(raw_image) -> bytes:
    image_bytes = base64.b64decode(raw_image.split(",")[1])
    return image_bytes


def encode_image(image_bytes: bytes) -> str:
    face_base64 = base64.b64encode(image_bytes).decode("utf-8")
    # this part is missing, i dont know why
    # it is important for the website to understand its format
    face_base64 = "data:image/jpeg;base64," + face_base64
    return face_base64
