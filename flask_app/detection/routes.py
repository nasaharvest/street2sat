import json
import random
import string
import sys
import zipfile
from pathlib import Path

import folium  # type: ignore
import shapefile  # type: ignore
from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    send_file,
    session,
    url_for,
)
from flask_login import current_user  # type: ignore
from werkzeug.utils import secure_filename

from street2sat_utils.client import Prediction, calculate_crop_coords

from ..forms import ChoosePicture, TestDataForm, UploadToDatabaseForm
from ..models import Image, UploadedImage
from ..utils import current_time

sys.path.insert(1, "./street2sat_utils")


model = Blueprint("model", __name__)


def generate_marker(
    pred: Prediction, color: str = "lightgray", use_estimate: bool = False
):
    if use_estimate:
        coord = list(pred.crop_coord.values())[0]
    else:
        coord = pred.coord
    time = pred.time
    return folium.Marker(
        coord,
        popup=f"<i> {pred.name}\n{time.hour}:{time.minute}:{time.second}\nLocation:{coord}</i>",
        icon=folium.Icon(color=color),
    )


def generate_predictions():
    jpg_files = session.get("jpg_files", None)
    choose_picture = ChoosePicture(images=jpg_files)
    current_index = 0
    if choose_picture.validate_on_submit():
        selected_img = choose_picture.drop_down.data
        current_index = jpg_files.index(selected_img)

    preds = []
    for filename in jpg_files:
        file = Image.objects(name=filename).first()
        if file is None:
            flash("Sorry, session expired. please upload images again.")
            return redirect(url_for("model.prediction"))
        pred = Prediction.from_results_and_tags(
            results=json.loads(file.result),
            tags=file.tags,
            name=filename,
            img_bytes=file.img_data,
        )
        preds.append(pred)

    if len(preds) > 1:
        preds = calculate_crop_coords(preds)
        session["new_points"] = [p.crop_coord for p in preds]

    return preds, current_index, choose_picture


@model.route("/", methods=["GET", "POST"])
def index():
    return render_template("index.html")


@model.route("/info", methods=["GET", "POST"])
def info():
    return render_template("info.html")


@model.route("/download_labels")
def download_labels():
    path = "./static/classes.txt"
    return send_file(path, as_attachment=True)


@model.route("/download_shapefile")
def download_shapefile():
    new_points = session["new_points"]
    print("NEW POINTS")
    print(new_points)

    letters = string.ascii_letters
    uniq = "".join(random.choice(letters) for _ in range(5))
    target = "./temp/" + uniq

    # Create shapefile
    w = shapefile.Writer(target=f"{target}_shapefile", shape=shapefile.POINT)
    w.field("Latitude", "N", decimal=30)
    w.field("Longitude", "N", decimal=30)
    w.field("Crop Type", "C")
    for crops in new_points:
        for crop, new_p in crops.items():
            w.point(new_p[1], new_p[0])
            w.record(new_p[0], new_p[1], crop)
    w.close()

    # Create projection file
    prj = open(f"{target}_shapefile.prj", "w")
    epsg = 'GEOGCS["WGS 84",'
    epsg += 'DATUM["WGS_1984",'
    epsg += 'SPHEROID["WGS 84",6378137,298.257223563]]'
    epsg += ',PRIMEM["Greenwich",0],'
    epsg += 'UNIT["degree",0.0174532925199433]]'
    prj.write(epsg)
    prj.close()

    zipf = zipfile.ZipFile(
        "./temp/" + uniq + "downloaded_shapefile.zip", "w", zipfile.ZIP_DEFLATED
    )

    shapefile_paths = [
        f"{target}_shapefile.{suffix}" for suffix in ["prj", "shp", "dbf", "shx"]
    ]
    for p in shapefile_paths:
        zipf.write(p)
        Path(p).unlink()
    zipf.close()

    return send_file(
        "../temp/" + uniq + "downloaded_shapefile.zip",
        mimetype="zip",
        attachment_filename="points.zip",
        as_attachment=True,
    )


@model.route("/upload", methods=["GET", "POST"])
def upload():
    form = UploadToDatabaseForm()
    if form.validate_on_submit():
        jpg_files = form.files.data
        txt_files = form.txt_files.data

        for jpg in jpg_files:
            if Path(jpg.filename).suffix.lower() not in [".jpg", ".jpeg"]:
                flash("Upload .jpg files!")
                return redirect(url_for("model.upload"))

        for txt in txt_files:
            if Path(txt.filename).suffix.lower() != ".txt":
                flash("Upload .txt files!")
                return redirect(url_for("model.upload"))

        txt_names = [Path(t.filename).stem for t in txt_files]
        for file in jpg_files:
            upload = UploadedImage(user=current_user._get_current_object())
            upload.image_file.put(file.stream, content_type="jpg")
            try:
                if file.filename.endswith(".jpg"):
                    t_file_index = txt_names.index(file.filename[:-4])
                elif file.filename.endswith(".jpeg"):
                    t_file_index = txt_names.index(file.filename[:-5])
                else:
                    raise Exception("Bruh whats going on?")
            except Exception:
                flash("Must upload a matching txt file for each jpg.")
                return redirect(url_for("model.upload"))

            upload.text_file.put(txt_files[t_file_index].stream, content_type="txt")
            upload.save()
            flash("Succesfully Uploaded!")
            return redirect(url_for("model.upload"))
    return render_template("upload.html", form=form)


@model.route("/prediction", methods=["GET", "POST"])
def prediction():
    form = TestDataForm()
    if not form.validate_on_submit():
        print("Form not validated!")
        return render_template("prediction.html", form=form)

    jpg_files = []
    letters = string.ascii_letters
    uniq = "".join(random.choice(letters) for _ in range(5))
    uniq = "upload_" + uniq + "_"

    if len(form.files.data) > 20:
        flash("More than 20 files detected, only running on the first 20.")

    for file in form.files.data[:20]:
        # for file in form.files.data[:]:
        file_filename = uniq + secure_filename(file.filename)
        if Path(file_filename).suffix.lower() not in [".jpg", ".jpeg"]:
            flash("Please upload all .jpg or .jpeg files!")
            return redirect(url_for("model.prediction"))

        try:
            pred = Prediction.from_img_bytes(
                img_bytes=file.stream, name=file_filename, close=False
            )
        except ValueError as e:
            flash(str(e))
            return redirect(url_for("model.prediction"))

        tag_dict = {
            "coord": pred.coord,
            "time": pred.time,
            "focal_length": pred.focal_length,
            "pixel_height": pred.pixel_height,
        }
        img = Image(
            name=file_filename,
            uploadtime=current_time(),
            tags=tag_dict,
            takentime=pred.time,
            result=json.dumps(pred.results),
        )
        img.img_data.put(file.stream, content_type="jpg")
        img.save()
        jpg_files.append(file_filename)
    # save current session jpg files to cookie
    session["jpg_files"] = jpg_files
    return redirect(url_for("model.display"))


@model.route("/display", methods=["GET", "POST"])
def display():
    preds, c_i, choose_picture = generate_predictions()
    selected = preds[c_i]
    map = folium.Map(location=selected.coord, zoom_start=17, tiles="OpenStreetMap")
    is_multiple_preds = len(preds) > 1

    for i, pred in enumerate(preds):
        color = "black" if i == c_i else "gray"
        generate_marker(pred, color=color).add_to(map)
        if is_multiple_preds:
            generate_marker(pred, color="red", use_estimate=True).add_to(map)

    kwargs = {
        "template_name_or_list": "display.html",
        "imgs": choose_picture,
        "image": preds[c_i].plot_labels(to_base_64=True),
        "map": map._repr_html_(),
        "info": selected.distances,
    }

    if preds[c_i].distances == {}:
        flash(f"No crops found for {selected.name}")
    elif is_multiple_preds:
        crop_coords = list(selected.crop_coord.values())[0]
        link = f"https://www.google.com/maps/search/?api=1&query={crop_coords[0]},{crop_coords[1]}"
        crop_on_gm = list(selected.distances.keys())[0]
        kwargs["link_to_gm"] = (link, crop_on_gm)

    return render_template(**kwargs)
