from flask_login import UserMixin  # type: ignore

from . import db, login_manager


@login_manager.user_loader
def load_user(user_id):
    return User.objects(username=user_id).first()


class User(db.Document, UserMixin):
    username = db.StringField(required=True, unique=True)
    email = db.EmailField(required=True, unique=True)
    password = db.StringField(required=True)
    # Returns unique string identifying our object

    def get_id(self):
        return self.username


class Image(db.Document):
    name = db.StringField(required=True, unique=True)
    img_data = db.ImageField()
    uploadtime = db.DateTimeField()
    tags = db.DictField()
    takentime = db.DateTimeField()
    result = db.StringField()


class UploadedImage(db.Document):
    user = db.ReferenceField(User, required=False)
    image_file = db.FileField(required=False)
    text_file = db.FileField(required=False)
