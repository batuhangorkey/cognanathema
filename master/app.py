from flask import Flask

import os
import dotenv
import cv2
import logging
import sys

dotenv.load_dotenv("../.env")

app = Flask(__name__)

# LOGGING
logger = logging.getLogger("my_logger")
logger.setLevel(logging.INFO)

c_handler = logging.StreamHandler()
file_handler = logging.FileHandler(
    "master/webapp.log", mode="w", encoding="utf-8"
)
# handler.setLevel(logging.INFO)

c_format = logging.Formatter("%(threadName)-20s - %(message)s")
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

# Database
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

db: SQLAlchemy = SQLAlchemy()
db.init_app(app)

migrate = Migrate(app, db)

# flask db init
# flask db migrate -m comment
# flask db upgrade

# FLASK-SECURITY
# DID NOT WORK. I even installed flask security too package.
# Probably my fault.. I will switch to using FLASK-LOGIN

# from master.models import User, Role

# user_datastore = SQLAlchemyUserDatastore(db, User, Role)
# security = Security(app, user_datastore)

from master import cognaface
cognaface.init()

logger.info(cognaface.VECTOR_ARRAY.shape)
logger.info(cognaface.ID_ARRAY)

from master import extensions

# INIT ROUTES
from master import routes

# Blueprints
from master.api import api

app.register_blueprint(api, url_prefix="/api")


if __name__ == "__main__":
    app.run(port=5000, debug=True)
