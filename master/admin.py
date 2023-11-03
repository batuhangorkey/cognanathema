from flask_admin.contrib.sqla import ModelView
from master.models import User, Identity
from master.extensions import admin_app
from master.app import db

admin_app.add_view(ModelView(User, db.session))
admin_app.add_view(ModelView(Identity, db.session))
