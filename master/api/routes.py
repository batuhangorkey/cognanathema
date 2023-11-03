import base64
import os
import secrets
from datetime import datetime, timedelta
from io import BytesIO
from time import time
from typing import List

import magic
import numpy as np
from flask import Blueprint, abort, jsonify, request, session
from flask_login import current_user, logout_user
from flask_socketio import join_room
from flask_sqlalchemy.query import Query
from h11 import Response
from PIL import Image
from sympy import timed
from werkzeug.datastructures import FileStorage

from master.api import api
from master.app import app, db, logger, socketio
from master.cognaface import draw_face, get_face, recognizer
from master.models import Detection, Identity, User

MAX_FILE_SIZE = 16 * 1e3


def check_json(func):
    def wrapper():
        data = request.json
        if not data:
            return jsonify("JSON missing"), 400
        return func()

    return wrapper


def check_id(func):
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
    def wrapper():
        data = request.json
        if not data:
            return jsonify("JSON missing"), 400
        id = data.get("id")
        if not id or id == "":
            return jsonify("ID missing"), 400
        return func()

    return wrapper


@socketio.on("video_data")
def handle_video_data(data):
    then = time()
    image_data = data["image_data"]

    image_bytes = base64.b64decode(image_data.split(",")[1])

    stream = BytesIO(image_bytes)
    image = Image.open(stream)
    image = draw_face(image)
    stream.seek(0)
    stream.truncate(0)
    image.save(stream, "jpeg")
    transformed_image = encode_image(stream.getvalue())

    print(timedelta(seconds=(time() - then)).microseconds // 1000)

    socketio.emit("transformed_image", {"transformed_image": transformed_image})


@socketio.on("start_stream")
def handle_start_stream():
    logger.info("Starting a live stream requested by client id: %s" % request.sid)

    socketio.emit("start_stream")


@socketio.on("live_stream")
def handle_live_stream(data):
    data = encode_image(data)

    socketio.emit("recv_live_stream", {"frame": data})


@check_id
@api.route("/detection", methods=["POST", "DELETE"])
def detection():
    id = request.json["id"]
    det: Detection = Detection.query.get_or_404(id)
    if request.method == "DELETE":
        db.session.delete(det)
        db.session.commit()
        return jsonify("Successfully deleted"), 200

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
    detections_q: Query = Detection.query.filter(Detection.timestamp >= one_day_ago)
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
@api.route("/register/face", methods=["POST"])
def register_face():
    # A face is sent, then it is registered to the user
    data = request.json
    image_data: str = data.get("image")
    # data comes with a leading part, it tells the type
    image_bytes = base64.b64decode(image_data.split(",")[1])

    if not sanitize_file(image_bytes):
        return jsonify("File not safe"), 400

    user: User = current_user

    stream = BytesIO(image_bytes)
    image = Image.open(stream)

    filename = secrets.token_urlsafe(4) + ".jpg"

    filepath = os.path.join("face", filename)
    fullpath = os.path.join(app.root_path, "uploads", "face", filename)

    if os.path.exists(fullpath):
        logger.warning("Path exists at %s" % fullpath)
        return jsonify({"result": "failed"}), 400

    image.save(fullpath)

    data = {"registered_face_path": filepath}
    identity = Identity.query.filter(Identity.name == user.username).first()
    if not identity:
        identity = Identity(name=user.username, data=data)

    return jsonify({"result": "success"}), 200


@api.route("/upload", methods=["POST"])
def upload():
    # TODO: ORDER AND GROUP THE SAME PEOPLE,
    # OTHERWISE MAIN PAGE IS FILLED WITH THE SAME HUMAN
    # TODO: MOVE THIS TO SOMEWHERE ELSE AND REWRITE, THIS CODE IS UGLY
    logger.info("Remote address: %s" % request.remote_addr)

    uploaded_file = request.files.get("file")
    timestamp = request.form.get("timestamp")
    face_detection_time = request.form.get("face_detection_time")

    if not uploaded_file:
        return jsonify("Missing file"), 400

    if not sanitize_file(uploaded_file):
        return jsonify("File is not safe"), 400

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

    filename = secrets.token_urlsafe(32) + ".jpg"
    path = os.path.join(app.root_path, "uploads", filename)

    try:
        uploaded_file.save(path)
        PIL_img = Image.open(path).convert("L")
    except Exception as e:
        logger.warning(e)
        if os.path.exists(path):
            logger.info(f"Removed file at: {path}")
            os.remove(path)
        return jsonify(f"Error: {e}"), 400

    img_numpy = np.array(PIL_img, "uint8")
    id, confidence = recognizer.predict(img_numpy)

    identity = Identity.query.get_or_404(id)
    logger.info("ID: %s, Confidence: %s" % (identity, confidence))

    face_recognition = elapsed_time(timestamp) - server_delay

    new_det = Detection(timestamp=timestamp, filepath=filename)  # type: ignore

    if confidence > 70:
        # TODO: IDEA: weak identites
        print(f"Weak identity: {identity}")
    else:
        # Identity found
        # see if we detected this human in the last one minute
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
