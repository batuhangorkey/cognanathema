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

cap = cv2.VideoCapture(0)
cap.set(3, 640)
cap.set(4, 480)

faceCascade = cv2.CascadeClassifier("cascades/haarcascade_frontalface_default.xml")
smileCascade = cv2.CascadeClassifier("cascades/haarcascade_smile.xml")
eyeCascade = cv2.CascadeClassifier("cascades/haarcascade_eye_tree_eyeglasses.xml")

DELAY = 10
REQUEST_TIMEOUT = 10
SERVER_ADDRESS = "http://127.0.0.1:5000/upload"


def denoise(frame):
    denoised = cv2.fastNlMeansDenoising(frame, None, 10, 10, 7)
    cv2.imshow("Denoised Camera", denoised)
    return denoised


def grayscale(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    cv2.imshow("Gray Camera", gray)
    return


def detect_faces():
    faces = faceCascade.detectMultiScale(
        gray, scaleFactor=1.3, minNeighbors=5, minSize=(150, 150)
    )
    for x, y, w, h in faces:
        cropped_face = gray[y : y + h, x : x + w]
        smiles = smileCascade.detectMultiScale(
            cropped_face, scaleFactor=1.3, minNeighbors=5, minSize=(50, 50)
        )
        smiles = [(box[0] + x, box[1] + y, box[2], box[3]) for box in smiles]
        draw_bboxes(smiles)
        
        eyes = eyeCascade.detectMultiScale(
            cropped_face, scaleFactor=1.3, minNeighbors=5, minSize=(50, 50)
        )
        eyes = [(box[0] + x, box[1] + y, box[2], box[3]) for box in eyes]
        draw_bboxes(eyes)
        
    draw_bboxes(faces)
    return faces


def detect_smile():
    pass


def draw_bboxes(boxes):
    for x, y, w, h in boxes:
        p1 = (x, y)
        p2 = (x + w, y + h)
        cv2.rectangle(frame, p1, p2, (255, 0, 0), 2)


def crop_faces(frame, faces):
    frame_ = frame.copy()
    cropped = []
    boxes = []
    for x, y, w, h in faces:
        cropped_face = frame_[y : y + h, x : x + w]

        # Recognizing code
        # for demo purposes
        crop_gray = cv2.cvtColor(cropped_face, cv2.COLOR_BGR2GRAY)
        id, confidence = recognizer.predict(crop_gray)
        if confidence < 100:
            id = id
            confidence = "  {0}%".format(round(100 - confidence))
        else:
            id = "unknown"
            confidence = "  {0}%".format(round(100 - confidence))
        cv2.putText(frame, str(confidence), (x + 5, y + h - 5), font, 1, (255, 0, 0), 1)
        # END

        cv2.putText(frame, str(id), (x + 5, y - 5), font, 1, (255, 0, 0), 2)
        cropped.append(cropped_face)
        box = np.array((x, y, w, h), dtype=int).reshape((2, 2))
        boxes.append(box)

    return cropped


def capture_faces(cropped_faces):
    for _ in cropped_faces:
        post_face(_)
        cv2.imshow("Face", _)


def post_face(img):
    ret, img_bytes = cv2.imencode(".jpg", img)
    files = {"file": ("photo.jpg", img_bytes)}

    start_to_post = time.time() - loop_start_time
    start_to_post = datetime.timedelta(seconds=start_to_post)
    print(start_to_post.microseconds)

    timestamp = datetime.datetime.utcnow().ctime()

    payload = {
        "timestamp": timestamp,
        "face_detection_time": datetime.timedelta(seconds=face_time).microseconds,
    }

    data = json.dumps(payload)
    response = requests.post(
        SERVER_ADDRESS, files=files, data=payload, timeout=REQUEST_TIMEOUT
    )

    print(response.json())


def capture_picture():
    pass


if __name__ == "__main__":
    recognizer = cv2.face.LBPHFaceRecognizer.create()
    recognizer.read("trainer/trainer.yml")

    font = cv2.FONT_HERSHEY_SIMPLEX
    loop_start_time = time.time()
    loop_end_time = loop_start_time
    timer = loop_start_time
    face_time: float = 0.0

    captured = False
    frame_times = deque([], 1000)

    # display_process = multiprocessing.Process(target=display)

    while True:
        loop_start_time = time.time()
        ret, frame = cap.read()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if not ret:
            print("Failed to grab frame")
            continue

        faces = detect_faces()

        if len(faces) > 0:
            face_time = time.time() - loop_start_time
            faces = crop_faces(frame, faces)
            if loop_start_time - timer > DELAY and captured:
                captured = False
            if not captured:
                print(f"Face detected! {len(faces)}")
                # capture_faces(faces)
                captured = True
                timer = time.time()

        loop_end_time = time.time()
        delta_time = loop_end_time - loop_start_time
        frame_times.append(1 / delta_time)
        avg = np.average(frame_times)
        cv2.putText(
            frame,
            f"Fps: {avg:.2f}",
            (30, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (255, 0, 0),
            2,
            cv2.LINE_AA,
            False,
        )

        cv2.imshow("Camera", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
