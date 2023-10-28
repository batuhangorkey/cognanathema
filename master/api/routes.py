import base64
from datetime import datetime, timedelta
from io import BytesIO
from typing import List
from PIL import Image
from flask import Blueprint, jsonify, request, abort
from h11 import Response
import magic
from . import api
from master.models import Detection
from master.app import db, logger
from master.cognaface import get_face
from flask_sqlalchemy.query import Query
from werkzeug.datastructures import FileStorage

MAX_FILE_SIZE = 16 * 1e6


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
    face_base64 = base64.b64encode(face_binary_data).decode('utf-8')
    # this part is missing, i dont know why
    # it is important for the website to understand its format
    face_base64 = 'data:image/jpeg;base64,' + face_base64

    return jsonify({"face": face_base64}), 200


@check_json
@api.route("/register/face", methods=["POST"])
def register_face():
    # A face is sent, then it is registered to the user
    data = request.json
    image_data: str = data.get("image")
    # data comes with a leading part
    image_bytes = base64.b64decode(image_data.split(",")[1])
    
    if not sanitize_file(image_bytes):
        return jsonify("File not safe"), 400
    
    stream = BytesIO(image_bytes)
    image = Image.open(stream)
    face = get_face(image)
    if face is None:
        return jsonify({"Error": "Face not found"}), 400
    logger.info("Face found")
    stream.seek(0)
    stream.truncate(0)
    face.save(stream, "jpeg")
    face_binary_data = stream.getvalue()
    face_base64 = base64.b64encode(face_binary_data).decode('utf-8')
    # this part is missing, i dont know why
    # it is important for the website to understand its format
    face_base64 = 'data:image/jpeg;base64,' + face_base64

    return jsonify({"face": face_base64}), 200
    


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
