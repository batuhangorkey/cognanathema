from flask import redirect, url_for

from flask_admin import Admin
from flask_login import LoginManager

from master.app import app
from master.models import User

admin_app = Admin(app, name="Admin Panel", template_mode="bootstrap4")

from master import admin

login_manager = LoginManager(app)
login_manager.login_view = "login"


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)
