import datetime
import json
import logging
import multiprocessing
import os
import time
from collections import deque

import cv2
import numpy as np
import requests
from deepface import DeepFace
from IPython.display import clear_output, display
from matplotlib import pyplot as plt
from PIL import Image
from scipy.spatial import distance
from torch import Value

from master.app import app
from master.models import Detection, Identity


logger = logging.getLogger("my_logger")

VECTOR_ARRAY = np.zeros(0)
ID_ARRAY = np.zeros(0)


def init():
    global VECTOR_ARRAY
    global ID_ARRAY
    conf = []
    id_list = []
    with app.app_context():
        identities = Identity.query.all()
    for identity in identities:
        if isinstance(identity.data, dict) and identity.data.get(
            "face_vector"
        ):
            vector = identity.data.get("face_vector")
            id_list.append(identity.id)
            conf.append(vector)

    VECTOR_ARRAY = np.array(conf)
    ID_ARRAY = np.array(id_list, dtype=np.uint)


class Cogna:
    pass


def compute_similarity(vector):
    cosine_distance = np.apply_along_axis(
        lambda x: distance.cosine(x, vector), axis=1, arr=VECTOR_ARRAY
    )
    return cosine_distance


def find_identity(vector) -> int | None:
    dis = compute_similarity(vector)
    i = np.argmin(dis)
    f = dis[i]
    if f < 0.3:
        return int(ID_ARRAY[i])
    else:
        return None


def get_face_vector(image: Image.Image):
    """
    aligned face image to vector
    """
    arr = np.array(image)[:, :, ::-1]
    logger.info(f"Shape of face image: {arr.shape}")

    vector = DeepFace.represent(
        arr, model_name="VGG-Face", detector_backend="skip"
    )[0]["embedding"]
    return np.array(vector)


def get_face(image: Image.Image) -> Image.Image | None:
    frame = np.asarray(image)

    try:
        faces = DeepFace.extract_faces(
            frame[:, :, ::-1],
            enforce_detection=True,
            align=True,
            detector_backend="ssd",
        )
    except ValueError:
        return None

    face = (faces[0]["face"] * 255).astype(np.uint8)

    face = Image.fromarray(face)
    return face


def draw_face(image: Image.Image):
    gray = image.convert("L")
    gray = np.array(gray, dtype=np.uint8)

    faces = faceCascade.detectMultiScale(
        gray, scaleFactor=1.3, minNeighbors=5, minSize=(50, 50)
    )

    if len(faces) < 1:
        return image

    arr = np.array(image, dtype=np.uint8)

    for x, y, w, h in faces:
        p1 = (x, y)
        p2 = (x + w, y + h)
        cv2.rectangle(arr, p1, p2, (255, 0, 0), 2)

    image = Image.fromarray(arr)

    return image
