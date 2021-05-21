# 3rd-party packages
from flask import Flask, render_template, request, redirect, url_for
from flask_mongoengine import MongoEngine
from flask_login import (
    LoginManager,
    current_user,
    login_user,
    logout_user,
    login_required,
)
from flask_bcrypt import Bcrypt
from werkzeug.utils import secure_filename

# stdlib
from datetime import datetime
import os
from apscheduler.schedulers.background import BackgroundScheduler
import shutil
# local

db = MongoEngine()
login_manager = LoginManager()
bcrypt = Bcrypt()

from .users.routes import users
from .movies.routes import model

def page_not_found(e):
    return render_template("404.html"), 404

def remove_folders():
    print('removing folders')
    print('Before', os.listdir('./temp'))
    for dir in os.listdir('./temp'):
        if os.path.isdir(os.path.join('./temp/', dir)):
            path_to_remove = os.path.join('./temp', dir)
            shutil.rmtree(path_to_remove)
    print('After', os.listdir('./temp'))

sched = BackgroundScheduler(daemon=True)
sched.add_job(remove_folders,'interval', minutes=5,id='remove_temp_folders')
sched.start()

def create_app(test_config=None):
    app = Flask(__name__)

    app.config.from_pyfile("config.py", silent=False)
    if test_config is not None:
        app.config.update(test_config)

    app.config["MONGODB_HOST"] = os.getenv("MONGODB_HOST")

    db.init_app(app)
    login_manager.init_app(app)
    bcrypt.init_app(app)
    # app.register_blueprint(main)
    app.register_blueprint(users)
    app.register_blueprint(model)
    app.register_error_handler(404, page_not_found)

    # login_manager.login_view = "main.login"
    login_manager.login_view = "users.login"

    return app
