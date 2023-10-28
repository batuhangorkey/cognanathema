import datetime
import json
import multiprocessing
import time
from collections import deque

import cv2
import numpy as np
import requests
from IPython.display import clear_output, display
from matplotlib import pyplot as plt
from PIL.Image import Image

faceCascade = cv2.CascadeClassifier("cascades/haarcascade_frontalface_default.xml")
smileCascade = cv2.CascadeClassifier("cascades/haarcascade_smile.xml")
eyeCascade = cv2.CascadeClassifier("cascades/haarcascade_eye_tree_eyeglasses.xml")


def get_face(image: Image):
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
