import base64
import io

from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import (  # type: ignore
    current_user,
    login_required,
    login_user,
    logout_user,
)

from .. import bcrypt
from ..forms import LoginForm, RegistrationForm, UpdateUsernameForm
from ..models import User

users = Blueprint("users", __name__)


@users.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("model.index"))

    form = RegistrationForm()
    if form.validate_on_submit():
        hashed = bcrypt.generate_password_hash(form.password.data).decode("utf-8")
        user = User(username=form.username.data, email=form.email.data, password=hashed)
        user.save()

        return redirect(url_for("users.login"))

    return render_template("register.html", title="Register", form=form)


@users.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("model.index"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.objects(username=form.username.data).first()

        if user is not None and bcrypt.check_password_hash(
            user.password, form.password.data
        ):
            login_user(user)
            return redirect(url_for("users.account"))
        else:
            flash("Login failed. Check your username and/or password")
            return redirect(url_for("users.login"))

    return render_template("login.html", title="Login", form=form)


@users.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("model.index"))


@users.route("/account", methods=["GET", "POST"])
@login_required
def account():
    username_form = UpdateUsernameForm()

    if username_form.validate_on_submit():
        # current_user.username = username_form.username.data
        current_user.modify(username=username_form.username.data)
        current_user.save()
        return redirect(url_for("users.account"))

    return render_template(
        "account.html",
        title="Account",
        username_form=username_form,
    )


# @users.route("/user/<username>")
# @login_required
# def user_detail(username):
#     user = User.objects(username=current_user.username).first()
#     user_audios = AudioFile.objects(user=user)
#
#
#     encoded = []
#     for a in user_audios:
#         p = a.prediction
#         t = a.truth
#         bytes_im = io.BytesIO(a.audio.read())
#         audio_encoded = base64.b64encode(bytes_im.getvalue()).decode()
#         encoded.append({'pred': p, 'truth': t, 'data': audio_encoded})
#
#     return render_template("user_detail.html", username=username, user_audios = encoded)
