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


# class Review(db.Document):
#     commenter = db.ReferenceField(User, required=True)
#     content = db.StringField(required=True, min_length=5, max_length=500)
#     date = db.StringField(required=True)
#     imdb_id = db.StringField(required=True, min_length=9, max_length=9)
#     movie_title = db.StringField(required=True, min_length=1, max_length=100)

# class AudioFile(db.Document):
#     audio = db.FileField(required = False)
#     user = db.ReferenceField(User, required = False)
#     prediction = db.StringField(required = False)
#     truth = db.StringField(required = False)
#
#
# class Accuracy(db.Document):
#     correct = db.IntField(required = True)
#     num_tries = db.IntField(required = True)
#     name = db.StringField(required = True)
