from flask import Blueprint, render_template, url_for, redirect, request, flash, session, send_file
from flask_login import current_user

# from .. import movie_client
from ..forms import UploadToDatabaseForm, TestDataForm, ChoosePicture
from ..models import User
from ..utils import current_time
import io
import base64
import os
from pydub import AudioSegment
import pydub
from werkzeug.utils import secure_filename
from ..client import *
import random
import string
import folium
import exifread
from ..exif_utils import *
import collections


model = Blueprint("model", __name__)


@model.route("/", methods=["GET", "POST"])
def index():
    return render_template("index.html")

@model.route("/info", methods = ["GET", "POST"])
def info():
    return render_template("info.html")

@model.route("/download_labels")
def download_labels():
    path = './static/classes.txt'
    return send_file(path, as_attachment=True)


@model.route("/upload", methods = [ "GET", "POST"])
def upload():
    form = UploadToDatabaseForm()
    if form.validate_on_submit():
        jpg_files = []
        for file in form.files.data:
            file_filename = secure_filename(file.filename)
            # data.save(os.path.join(app.config['UPLOAD_FOLDER'], data_filename))
            files_filenames.append(file_filename)
    return render_template("upload.html", form = form)


@model.route("/prediction", methods = ["GET", "POST"])
def prediction():
    form = TestDataForm()
    if form.validate_on_submit():
        from .. import sched
        sched.reschedule_job('remove_temp_folders', trigger='interval', minutes=5)
        jpg_files = []
        letters = string.ascii_letters
        uniq = ( ''.join(random.choice(letters) for i in range(10)) )
        file_path = './temp/' + uniq + '/'
        os.mkdir(file_path)
        for file in form.files.data:
            file_filename = secure_filename(file.filename)
            if not (file_filename.split('.')[-1].lower() == 'jpg'):
                flash("Please upload all .jpg files!")
                return redirect(url_for("model.prediction"))
            file.save(os.path.join(file_path, file_filename))
            jpg_files.append(file_filename)
        predict(file_path, file_path)
        session['file_path'] = file_path
        session['jpg_files'] = jpg_files
        if len(form.files.data) == 1:
            return redirect(url_for("model.displayone"))
        return redirect(url_for("model.display"))
    return render_template("prediction.html", form = form)

@model.route("/displayone",methods = ["GET", "POST"])
def displayone():
    from .. import sched
    sched.reschedule_job('remove_temp_folders', trigger='interval', minutes=5)
    jpg_files = session.get('jpg_files', None)
    choose_picture = ChoosePicture(images = jpg_files)
    file_path = session.get('file_path', None)
    img_path = os.path.join(file_path, jpg_files[0])
    label_path = os.path.join(file_path, 'exp', 'labels', jpg_files[0].split('.')[0] + '.txt')

    f = open(img_path, 'rb')
    tags = exifread.process_file(f)
    lat_long = get_exif_location(tags)
    time = get_exif_datetime(tags)

    map = folium.Map(location = lat_long, zoom_start = 13, tiles = "Stamen Terrain")
    folium.Marker(lat_long, popup="<i> {}\n{}:{}:{}</i>".format(jpg_files[0], time.tm_hour, time.tm_min, time.tm_sec), icon=folium.Icon(color='lightgray')).add_to(map)



    if not os.path.exists(label_path):
        flash("No crops found for {}".format(selected_img))
        s = get_image(img_path)
        map_html = map._repr_html_()
        return render_template("display.html", imgs = choose_picture, image = s, map = map_html)
    else:
        info = get_distance_meters(img_path, label_path)
        s = plot_labels(img_path, label_path)
        map_html = map._repr_html_()
        return render_template("display.html", imgs = choose_picture, image = s, map = map_html, info = info)



@model.route("/display", methods = ["GET", "POST"])
def display():
    from .. import sched
    sched.reschedule_job('remove_temp_folders', trigger='interval', minutes=15)
    jpg_files = session.get('jpg_files', None)
    choose_picture = ChoosePicture(images = jpg_files)
    file_path = session.get('file_path', None)


    if choose_picture.validate_on_submit():
        selected_img = choose_picture.drop_down.data
        img_path = os.path.join(file_path, selected_img)
        label_path = os.path.join(file_path, 'exp', 'labels', selected_img.split('.')[0] + '.txt')
        file_time = session['file_time']
        file_coord = session['file_coord']
        file_distance = session['file_distance']
        bearings = session['file_bearings']
        new_points = session['new_points']

        map = folium.Map(location = file_coord[selected_img], zoom_start = 17, tiles = "OpenStreetMap")
        for file in jpg_files:
            time = file_time[file]
            if file != selected_img:
                folium.Marker(file_coord[file], popup="<i> {}\n{}:{}:{}</i>".format(file, time[3], time[4], time[5]), icon=folium.Icon(color='lightgray')).add_to(map)
            else:
                folium.Marker(file_coord[file], popup="<i> {}\n{}:{}:{}</i>".format(file, time[3], time[4], time[5]), icon=folium.Icon(color='black')).add_to(map)

        for file,crops in new_points.items():
            for crop, new_p in crops.items():
                folium.Marker(new_p, popup="<i> {}\n{}\n{}/i>".format(file, file_distance[file], bearings[file]), icon=folium.Icon(color='red')).add_to(map)


        if not os.path.exists(label_path):
            flash("No crops detected for {}".format(selected_img))
            s = get_image(img_path)
            map_html = map._repr_html_()
            return render_template("display.html", imgs = choose_picture, image = s, map = map_html)
        else:
            info = get_distance_meters(img_path, label_path)
            crop_on_gm = list(new_points[selected_img].keys())[0]
            link = 'https://www.google.com/maps/search/?api=1&query={},{}'.format(new_points[selected_img][crop_on_gm][0], new_points[selected_img][crop_on_gm][1])
            s = plot_labels(img_path, label_path)
            map_html = map._repr_html_()
            return render_template("display.html", imgs = choose_picture, image = s, map = map_html, info = info, link_to_gm = (link, crop_on_gm))

    # time:file
    file_time = {}
    # file:(lat,long)
    file_coord = {}
    # file:distance
    file_distance = {}

    map = None

    for file in jpg_files:
        img_path = os.path.join(file_path, file)
        label_path = os.path.join(file_path, 'exp', 'labels', file.split('.')[0] + '.txt')
        f = open(img_path, 'rb')
        tags = exifread.process_file(f)
        lat_long = get_exif_location(tags)
        time = get_exif_datetime(tags)

        if map == None:
            map = folium.Map(location = lat_long, zoom_start = 17, tiles = "OpenStreetMap")
        folium.Marker(lat_long, popup="<i> {}\n{}:{}:{}</i>".format(file, time.tm_hour, time.tm_min, time.tm_sec), icon=folium.Icon(color='lightgray')).add_to(map)
        file_time[time] = file
        file_coord[file] = lat_long

        if os.path.exists(label_path):
            distance = get_distance_meters(img_path, label_path)
            file_distance[file] = distance


    # bearings is file:bearing, new_points is file:translated point
    bearings, new_points = get_new_points(file_time, file_coord, file_distance)
    for file,crops in new_points.items():
        for crop, new_p in crops.items():
            folium.Marker(new_p, popup="<i> {}\n{}\n{}/i>".format(file, file_distance[file], bearings[file]), icon=folium.Icon(color='red')).add_to(map)

    # save all dictionaries to session
    #switch from time:file to file:time for serialization
    file_time = dict((y,x) for x,y in file_time.items())
    session['file_time'] = file_time
    session['file_coord'] = file_coord
    session['file_distance'] = file_distance
    session['file_bearings'] = bearings
    session['new_points'] = new_points
    map_html = map._repr_html_()
    return render_template("display.html", imgs = choose_picture, map = map_html)
