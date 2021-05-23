from flask import Blueprint, render_template, url_for, redirect, request, flash, session, send_file
from flask_login import current_user

# from .. import movie_client
from ..forms import UploadToDatabaseForm, TestDataForm, ChoosePicture
from ..models import User, Image
from ..utils import current_time
import io
import base64
import os
from werkzeug.utils import secure_filename
from ..client import *
import random
import string
import folium
import exifread
from ..exif_utils import *
import collections
import numpy
import cv2
import time
import json
import gc



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
        jpg_files = form.files.data
        txt_files = form.txt_files.data

        for jpg in jpg_files:
            if jpg.filename.split('.')[-1].lower() != 'jpg' and jpg.filename.split('.')[-1].lower() != 'jpeg':
                flash('Upload .jpg files!')
                return redirect(url_for("model.upload"))

        for txt in txt_files:
            if txt.filename.split('.')[-1].lower() != 'txt':
                flash('Upload .txt files!')
                return redirect(url_for("model.upload"))

        txt_names = [t.filename[:-4] for t in txt_files]
        for file in jpg_files:
            upload = UploadedImage(user = current_user._get_current_object())
            upload.image_file.put(file.stream, content_type = 'jpg')
            try:
                if file.filename.endswith('.jpg'):
                    t_file_index = txt_names.index(file.filename[:-4])
                elif file.filename.endswith('.jpeg'):
                    t_file_index = txt_names.index(file.filename[:-5])
                else:
                    raise Exception("Bruh whats going on?")
            except:
                flash('Must upload a matching txt file for each jpg.')
                return redirect(url_for("model.upload"))

            upload.text_file.put(txt_files[t_file_index].stream, content_type = 'txt')
            upload.save()
            flash('Succesfully Uploaded!')
            return redirect(url_for("model.upload"))
    return render_template("upload.html", form = form)


@model.route("/prediction", methods = ["GET", "POST"])
def prediction():
    form = TestDataForm()
    if form.validate_on_submit():
        jpg_files = []
        letters = string.ascii_letters
        uniq = ( ''.join(random.choice(letters) for i in range(5)) )
        uniq = 'upload_' + uniq + '_'


        if len(form.files.data) > 20:
            flash("More than 20 files detected, only running on the first 20.")

        for file in form.files.data[:20]:
            file_filename = secure_filename(file.filename)
            file_filename = uniq + file_filename

            if not ((file_filename.split('.')[-1].lower() == 'jpg') or (file_filename.split('.')[-1].lower() == 'jpeg')):
                flash("Please upload all .jpg or .jpeg files!")
                return redirect(url_for("model.prediction"))

            try:
                tags = exifread.process_file(file)
            except:
                flash("Exif tags could not be found for {}".format(file_filename))
                return redirect(url_for("model.prediction"))
            try:
                lat_long = get_exif_location(tags)
            except:
                flash("Latitude longitude could not be found for {}".format(file_filename))
                return redirect(url_for("model.prediction"))
            try:
                taken_time = get_exif_datetime(tags)
            except:
                flash("Time information could not be found for {}".format(file_filename))
                return redirect(url_for("model.prediction"))
            try:
                focal_length = get_exif_focal_length(tags)
            except:
                flash("Focal length information could not be found for {}".format(file_filename))
                return redirect(url_for("model.prediction"))
            try:
                pixel_height, pixel_width = get_exif_image_height_width(tags)
            except:
                flash("Image height/width information could not be found for {}".format(file_filename))
                return redirect(url_for("model.prediction"))

            tag_dict = {}
            tag_dict['lat_long'] = lat_long
            tag_dict['taken_time'] = taken_time
            tag_dict['focal_length'] = focal_length
            tag_dict['pixel_width'] = pixel_width
            tag_dict['pixel_height'] = pixel_height

            img = Image(name = file_filename, uploadtime = current_time(), tags = tag_dict, takentime = taken_time)
            img.img_data.put(file.stream, content_type = 'jpg')
            img.save()

            jpg_files.append(file_filename)

        results = predict(jpg_files)

        # save current session jpg files to cookie
        session['jpg_files'] = jpg_files

        for i,f in enumerate(jpg_files):
            img = Image.objects(name = f).first()
            # img.result = results.pandas().xyxy[i].to_json(orient="records")
            img.result = results[i]
            img.save()

        if len(form.files.data) == 1:
            return redirect(url_for("model.displayone"))
        return redirect(url_for("model.display"))
    return render_template("prediction.html", form = form)

@model.route("/displayone",methods = ["GET", "POST"])
def displayone():
    jpg_files = session.get('jpg_files', None)
    choose_picture = ChoosePicture(images = jpg_files)

    file = Image.objects(name = jpg_files[0]).first()
    if file == None:
        flash("Sorry, session expired. please upload images again.")
        return redirect(url_for("model.prediction"))
    lat_long = file.tags['lat_long']
    time = file.takentime
    focal_length = file.tags['focal_length']
    pixel_width = file.tags['pixel_width']
    pixel_height = file.tags['pixel_height']

    results = file.result
    results = json.loads(results)

    filestr = file.img_data.read()
    npimg = numpy.fromstring(filestr, numpy.uint8)
    img = cv2.imdecode(npimg, cv2.IMREAD_UNCHANGED)
    img = img[:, :, ::-1] # BGR to RGB

    map = folium.Map(location = lat_long, zoom_start = 17, tiles = "OpenStreetMap")
    folium.Marker(lat_long, popup="<i> {}\n{}:{}:{}</i>".format(jpg_files[0], time.hour, time.minute, time.second), icon=folium.Icon(color='lightgray')).add_to(map)
    map_html = map._repr_html_()

    info = get_distance_meters(results, focal_length, pixel_width, pixel_height, lat_long)
    if info == {}:
        flash("No crops found for {}".format(jpg_files[0]))
    s = plot_labels(img, results)
    return render_template("display.html", imgs = choose_picture, image = s, map = map_html, info = info)

@model.route("/display", methods = ["GET", "POST"])
def display():
    jpg_files = session.get('jpg_files', None)
    choose_picture = ChoosePicture(images = jpg_files)

    if choose_picture.validate_on_submit():
        selected_img = choose_picture.drop_down.data
        file_time = session['file_time']
        file_coord = session['file_coord']
        file_distance = session['file_distance']
        bearings = session['file_bearings']
        new_points = session['new_points']

        map = folium.Map(location = file_coord[selected_img], zoom_start = 17, tiles = "OpenStreetMap")
        for file in jpg_files:
            time = file_time[file]
            if file != selected_img:
                folium.Marker(file_coord[file], popup="<i> {}\n{}:{}:{}</i>".format(file, time.hour, time.minute, time.second), icon=folium.Icon(color='lightgray')).add_to(map)
            else:
                folium.Marker(file_coord[file], popup="<i> {}\n{}:{}:{}</i>".format(file, time.hour, time.minute, time.second), icon=folium.Icon(color='black')).add_to(map)

        for file,crops in new_points.items():
            for crop, new_p in crops.items():
                folium.Marker(new_p, popup="<i> {}\n{}\n{}/i>".format(file, file_distance[file], bearings[file]), icon=folium.Icon(color='red')).add_to(map)

        map_html = map._repr_html_()

        file = Image.objects(name = selected_img).first()
        if file == None:
            flash("Sorry, session expired. please upload images again.")
            return redirect(url_for("model.prediction"))
        lat_long = file.tags['lat_long']
        time = file.takentime
        focal_length = file.tags['focal_length']
        pixel_width = file.tags['pixel_width']
        pixel_height = file.tags['pixel_height']

        results = file.result
        results = json.loads(results)

        filestr = file.img_data.read()
        npimg = numpy.fromstring(filestr, numpy.uint8)
        img = cv2.imdecode(npimg, cv2.IMREAD_UNCHANGED)
        img = img[:, :, ::-1] # BGR to RGB
        info = get_distance_meters(results, focal_length, pixel_width, pixel_height, lat_long)
        s = plot_labels(img, results)

        if info == {}:
            flash("No crops detected for {}".format(selected_img))
            return render_template("display.html", imgs = choose_picture, image = s, map = map_html, info = info)
        else:
            crop_on_gm = list(new_points[selected_img].keys())[0]
            link = 'https://www.google.com/maps/search/?api=1&query={},{}'.format(new_points[selected_img][crop_on_gm][0], new_points[selected_img][crop_on_gm][1])
            return render_template("display.html", imgs = choose_picture, image = s, map = map_html, info = info, link_to_gm = (link, crop_on_gm))

    # time:file
    file_time = {}
    # file:(lat,long)
    file_coord = {}
    # file:distance
    file_distance = {}

    map = None

    for file in jpg_files:
        filename = Image.objects(name = file).first()
        lat_long = filename.tags['lat_long']
        time = filename.takentime
        focal_length = filename.tags['focal_length']
        pixel_width = filename.tags['pixel_width']
        pixel_height = filename.tags['pixel_height']

        results = filename.result
        results = json.loads(results)


        if map == None:
            map = folium.Map(location = lat_long, zoom_start = 17, tiles = "OpenStreetMap")
        folium.Marker(lat_long, popup="<i> {}\n{}:{}:{}</i>".format(file, time.hour, time.minute, time.second), icon=folium.Icon(color='lightgray')).add_to(map)
        file_time[time] = file
        file_coord[file] = lat_long

        info = get_distance_meters(results, focal_length, pixel_width, pixel_height, lat_long)
        file_distance[file] = info


    # bearings is file:bearing, new_points is file:translated point
    bearings, new_points = get_new_points(file_time, file_coord, file_distance)
    for file,crops in new_points.items():
        for crop, new_p in crops.items():
            folium.Marker(new_p, popup="<i> {}\n{}\n{}/i>".format(file, file_distance[file], bearings[file]), icon=folium.Icon(color='red')).add_to(map)

    # save all dictionaries to session
    # switch from time:file to file:time for serialization
    file_time = dict((y,x) for x,y in file_time.items())
    session['file_time'] = file_time
    session['file_coord'] = file_coord
    session['file_distance'] = file_distance
    session['file_bearings'] = bearings
    session['new_points'] = new_points
    map_html = map._repr_html_()
    return render_template("display.html", imgs = choose_picture, map = map_html)
