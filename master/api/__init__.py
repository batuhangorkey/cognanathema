from flask import Blueprint, jsonify

api = Blueprint("api", __name__)

from . import routes
