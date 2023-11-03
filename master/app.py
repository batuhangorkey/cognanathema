from flask import Flask

import os
import dotenv
import cv2

dotenv.load_dotenv("../.env")

app = Flask(__name__)

# LOGGING

import logging
import sys

logger = logging.getLogger("my_logger")
logger.setLevel(logging.INFO)

c_handler = logging.StreamHandler()
file_handler = logging.FileHandler("master/webapp.log", mode="a")
# handler.setLevel(logging.INFO)

c_format = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
file_handler.setFormatter(c_format)
c_handler.setFormatter(c_format)

logger.addHandler(file_handler)
logger.addHandler(c_handler)

# Flask Config
app.config[
    "SQLALCHEMY_DATABASE_URI"
] = f'sqlite:///{os.path.join(app.root_path, "master.db")}'
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")
app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "uploads")

# Socketio
from flask_socketio import SocketIO

socketio = SocketIO(app)

# Database
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

db: SQLAlchemy = SQLAlchemy()
db.init_app(app)

migrate = Migrate(app, db)

# Blueprints
from .api import api

app.register_blueprint(api, url_prefix="/api")


# FLASK-SECURITY
# DID NOT WORK. I even installed flask security too package.
# Probably my fault.. I will switch to using FLASK-LOGIN

# from master.models import User, Role

# user_datastore = SQLAlchemyUserDatastore(db, User, Role)
# security = Security(app, user_datastore)

from master import extensions

# INIT ROUTES
from master import routes
from master import cognaface

if __name__ == "__main__":
    socketio.run(app, port=5000, debug=True, use_reloader=True, log_output=False)
