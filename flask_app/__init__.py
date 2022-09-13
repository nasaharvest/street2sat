# 3rd-party packages
# stdlib
import datetime
import os
import sys

from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore
from flask import Flask, render_template
from flask_bcrypt import Bcrypt  # type: ignore
from flask_login import LoginManager  # type: ignore
from flask_mongoengine import MongoEngine  # type: ignore

db: MongoEngine = MongoEngine()
login_manager: LoginManager = LoginManager()
bcrypt = Bcrypt()

from .detection.routes import model  # noqa
from .models import Image  # noqa
from .users.routes import users  # noqa

sys.path.insert(1, "../street2sat_utils")


def page_not_found(e):
    return render_template("404.html"), 404


def remove_folders():
    print("removing images")
    now = datetime.datetime.now() - datetime.timedelta(minutes=30)
    Image.objects(uploadtime__lte=now).delete()

    for file in os.listdir("./temp"):
        if file != ".gitkeep":
            os.remove(os.path.join("./temp", file))


sched = BackgroundScheduler(daemon=True)
sched.add_job(remove_folders, "interval", minutes=5, id="remove_temp_folders")
sched.start()


def create_app(test_config=None):
    app = Flask(__name__)

    app.config.from_pyfile("config.py", silent=False)
    if test_config is not None:
        app.config.update(test_config)

    # app.config["MONGODB_HOST"] = os.getenv("MONGODB_HOST")

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
