from flask_admin.contrib.sqla import ModelView
from .models import User, Identity
from .app import admin_app, db

admin_app.add_view(ModelView(User, db.session))
admin_app.add_view(ModelView(Identity, db.session))
