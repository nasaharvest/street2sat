import string

from flask_login import current_user
from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField, FileRequired
from werkzeug.utils import secure_filename
from wtforms import (
    MultipleFileField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import (
    DataRequired,
    Email,
    EqualTo,
    InputRequired,
    Length,
    NumberRange,
    ValidationError,
)

from .models import User


class UploadToDatabaseForm(FlaskForm):
    files = MultipleFileField("JPG File(s) Upload")
    txt_files = MultipleFileField("Txt File(s) Upload")
    submit = SubmitField("Upload")


class TestDataForm(FlaskForm):
    files = MultipleFileField("JPG File(s) Upload")
    submit = SubmitField("Upload")


class ChoosePicture(FlaskForm):
    drop_down = SelectField("Choose Image", choices=[])
    go = SubmitField("Go")

    def __init__(self, images: list = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if images:
            for img in images:
                self.drop_down.choices.append((img, img))


class RegistrationForm(FlaskForm):
    username = StringField(
        "Username", validators=[InputRequired(), Length(min=1, max=40)]
    )
    email = StringField("Email", validators=[InputRequired(), Email()])
    password = PasswordField("Password", validators=[InputRequired(), Length(min=1)])
    confirm_password = PasswordField(
        "Confirm Password", validators=[InputRequired(), EqualTo("password")]
    )
    submit = SubmitField("Sign Up")

    def validate_username(self, username):
        user = User.objects(username=username.data).first()
        if user is not None:
            raise ValidationError("Username is taken")

    def validate_email(self, email):
        user = User.objects(email=email.data).first()
        if user is not None:
            raise ValidationError("Email is taken")


class LoginForm(FlaskForm):
    username = StringField("Username", validators=[InputRequired()])
    password = PasswordField("Password", validators=[InputRequired()])
    submit = SubmitField("Login")


class UpdateUsernameForm(FlaskForm):
    username = StringField(
        "New Username", validators=[InputRequired(), Length(min=1, max=40)]
    )
    submit = SubmitField("Update Username")

    def validate_username(self, username):
        if username.data != current_user.username:
            user = User.objects(username=username.data).first()
            if user is not None:
                raise ValidationError("That username is already taken")
