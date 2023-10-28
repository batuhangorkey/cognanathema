from flask import redirect, url_for
from master.app import app
from master.models import User
from flask_login import LoginManager

login_manager = LoginManager(app)
login_manager.login_view = "login"


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)
