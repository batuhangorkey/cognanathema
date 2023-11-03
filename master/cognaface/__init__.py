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
from IPython.display import clear_output, display
from matplotlib import pyplot as plt
from PIL import Image

from master.models import Detection

logger = logging.getLogger("my_logger")

faceCascade = cv2.CascadeClassifier("cascades/haarcascade_frontalface_default.xml")
smileCascade = cv2.CascadeClassifier("cascades/haarcascade_smile.xml")
eyeCascade = cv2.CascadeClassifier("cascades/haarcascade_eye_tree_eyeglasses.xml")

recognizer = cv2.face.LBPHFaceRecognizer.create()
recognizer.read("trainer/trainer.yml")


def get_face(image: Image.Image):
    gray = image.convert("L")
    gray = np.array(gray)
    faces = faceCascade.detectMultiScale(
        gray, scaleFactor=1.3, minNeighbors=5, minSize=(150, 150)
    )
    if len(faces) < 1:
        return None
    x, y, w, h = faces[0]
    face = image.crop((x, y, x + w, y + h))
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


def train():
    logger.info(__file__)
    face_samples = []
    ids = []

    dets = Detection.query.all()
    for det in dets:
        if det.identity:
            path = os.path.join("master/uploads/", det.filepath)
            PIL_img = Image.open(path).convert("L")
            img_numpy = np.array(PIL_img, "uint8")
            face_samples.append(img_numpy)
            ids.append(det.identity.id)
    os.makedirs("trainer", exist_ok=True)

    recognizer = cv2.face.LBPHFaceRecognizer.create()
    recognizer.train(face_samples, np.array(ids))

    recognizer.write("trainer/trainer.yml")
