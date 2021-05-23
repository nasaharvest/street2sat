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
import datetime
import os
from apscheduler.schedulers.background import BackgroundScheduler
import shutil
import sys
import gc
# os.environ["TORCH_INSTALL"] = "0"
# local

db = MongoEngine()
login_manager = LoginManager()
bcrypt = Bcrypt()
from .users.routes import users
from .detection.routes import model
from .models import Image

def page_not_found(e):
    return render_template("404.html"), 404

def remove_folders():
    print('removing images')
    print('Before')
    for img in Image.objects.all():
        print(img.name, img.uploadtime)

    now = datetime.datetime.now() - datetime.timedelta(minutes=15)
    Image.objects(uploadtime__lte = now).delete()
    print('After')
    for img in Image.objects.all():
        print(img.name, img.uploadtime)

    gc.set_debug(gc.DEBUG_LEAK)

    # local_vars = list(globals().items())
    # for var, obj in local_vars:
    #     print(var, sys.getsizeof(obj))
    #
    # local_vars = list(locals().items())
    # for var, obj in local_vars:
    #     print(var, sys.getsizeof(obj))

    # start_path = '.'
    # total_size = 0
    # for dirpath, dirnames, filenames in os.walk(start_path):
    #     for f in filenames:
    #         fp = os.path.join(dirpath, f)
    #         # skip if it is symbolic link
    #         if not os.path.islink(fp):
    #             total_size += os.path.getsize(fp)
    # print(os.listdir('.'))
    # for dir in os.listdir('.'):
    #     start_path = './' + dir
    #     total_size = 0
    #     for dirpath, dirnames, filenames in os.walk(start_path):
    #         for f in filenames:
    #             fp = os.path.join(dirpath, f)
    #             # skip if it is symbolic link
    #             if not os.path.islink(fp):
    #                 total_size += os.path.getsize(fp)
    #
    #     print('start_path', dir, total_size, 'bytes')

sched = BackgroundScheduler(daemon=True)
sched.add_job(remove_folders,'interval', minutes = 1, id='remove_temp_folders')
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
