import os
import cv2
import exifread
import numpy as np
import urllib.request
from time import sleep
import matplotlib.pyplot as plt
from pygeotile.tile import Tile, Point


# Constants
AMP = 2
ZOOM = 18
VALID_EXT = ["png", "jpg", "jpeg"]
FILE_NAMES = None
INPUT_DIR = "/home/btokas/data/Crops1/"
# ALT_DIR -  The corresponding previous images were in a different directory. Could be same directory if everything is in the same dir
ALT_DIR = "/home/btokas/data/Crops/"
OUT_DIR = "/home/btokas/data/Tiles/Crops1/"

# Helper Functions
def _convert_to_degrees(value):
    """
    Helper function to convert the GPS coordinates stored in the EXIF to degress in float format
    :param value:
    :type value: exifread.utils.Ratio
    :rtype: float
    """
    d = float(value.values[0].num) / float(value.values[0].den)
    m = float(value.values[1].num) / float(value.values[1].den)
    s = float(value.values[2].num) / float(value.values[2].den)

    return d + (m / 60.0) + (s / 3600.0)


def get_exif_location(exif_data):
    """
    Returns the latitude and longitude, if available, from the provided exif_data (obtained through get_exif_data above)
    """
    gps_latitude = exif_data["GPS GPSLatitude"]
    gps_latitude_ref = exif_data["GPS GPSLatitudeRef"]
    gps_longitude = exif_data["GPS GPSLongitude"]
    gps_longitude_ref = exif_data["GPS GPSLongitudeRef"]

    lat = _convert_to_degrees(gps_latitude)
    if gps_latitude_ref.values[0] != "N":
        lat = 0 - lat

    lon = _convert_to_degrees(gps_longitude)
    if gps_longitude_ref.values[0] != "E":
        lon = 0 - lon

    return lat, lon


def getOrthogonal(prev_pos, curr_pos, amp=3, flip=False):
    """
    Finds a point to the left (or right if flipped) based on
    current and previous position. Amp is just a scaling factor
    of the left pointing vector.
    """
    x_prev, y_prev = prev_pos
    x_curr, y_curr = curr_pos
    x_delta = x_curr - x_prev
    y_delta = y_curr - y_prev
    x_new = x_curr + int(y_delta * amp)
    y_new = y_curr - int(x_delta * amp)
    if flip:
        x_new = x_curr - int(y_delta * amp)
        y_new = y_curr + int(x_delta * amp)
    return (x_new, y_new)


def draw(img, prev_pos, curr_pos):
    img = cv2.circle(img, prev_pos, 1, (0, 0, 255), -1)
    img = cv2.circle(img, curr_pos, 1, (255, 0, 0), -1)
    img = cv2.arrowedLine(img, prev_pos, curr_pos, (0, 255, 0), 1)
    orth_pos = getOrthogonal(prev_pos, curr_pos)
    img = cv2.arrowedLine(img, curr_pos, orth_pos, (51, 255, 255), 1)
    return img


def getNewName(fname):
    """
    Get name for the previous frame
    """
    name = fname.split(".")[0].split(INPUT_DIR)[1].split("/")[-1]
    digit = "".join([i for i in name if i.isdigit()])
    num = len(digit)
    digit = str(int(digit) + 1).zfill(num)
    outName = ALT_DIR + "/".join(fname.split(INPUT_DIR)[1].split("/")[:-1]) + "/"
    return outName + "".join(i for i in name if not (i.isdigit())) + str(digit) + ".JPG"


def getGoogleXY(fname):
    with open(fname, "rb") as f:
        meta = exifread.process_file(f)
        lat, long = get_exif_location(meta)
        p = Point(lat, long)
        google_x, google_y = p.pixels(ZOOM)
    return google_x, google_y


def getTile(gx, gy, ZOOM):
    req = urllib.request.Request(
        f"https://mt0.google.com/vt/lyrs=s&hl=en&x={gx}&y={gy}&z={ZOOM}"
    )
    resp = urllib.request.urlopen(req)
    sleep(0.1)
    curr_tile = np.asarray(bytearray(resp.read()), dtype="uint8")
    curr_tile = cv2.imdecode(curr_tile, cv2.IMREAD_COLOR)
    return curr_tile


def createParent(name):
    parent_dir = "/".join(name.split("/")[:-1])
    if not (os.path.isdir(parent_dir)):
        os.makedirs(parent_dir)


# Main
files = []
for root, subdirs, img_names in os.walk(INPUT_DIR):
    for img_name in img_names:
        files.append(root + "/" + img_name)

names = None
if FILE_NAMES:
    with open(FILE_NAMES, "r") as f:
        names = f.readlines()[0].split(",")

if not (os.path.isdir(OUT_DIR)):
    os.mkdir(OUT_DIR)

missed_counts = 0
for num, file in enumerate(files):
    print(f"\rImage_Num = {num}/{len(files)}", end="")
    OUT_NAME = OUT_DIR + file.split(INPUT_DIR)[1]
    createParent(OUT_NAME)
    if os.path.exists(OUT_NAME):
        continue
    try:
        google_x_prev, google_y_prev = getGoogleXY(file)
    except Exception as e:
        print(f"\n{e}, current count: {missed_counts}")
        missed_counts += 1
        continue
    gx_prev, gy_prev = google_x_prev // 256, google_y_prev // 256
    x_prev, y_prev = google_x_prev % 256, google_y_prev % 256
    new_file = getNewName(file)
    try:
        google_x, google_y = getGoogleXY(new_file)
    except Exception as e:
        print(f"\n{e}, current count: {missed_counts}")
        missed_counts += 1
        continue
    gx, gy = google_x // 256, google_y // 256
    x, y = google_x % 256, google_y % 256
    if (gx_prev != gx) or (gy_prev != gy):
        print(f"\nTile Mismatch, current count: {missed_counts}")
        missed_counts += 1
        continue
    try:
        curr_tile = getTile(gx, gy, ZOOM)
    except Exception as e:
        print(f"\n Couldn't Fetch Tile, current_count: {missed_counts}")
        missed_counts += 1
        continue
    frame = cv2.imread(file)
    frame = cv2.resize(frame, (256 * AMP, 256 * AMP))
    img = curr_tile.copy()
    img = cv2.resize(img, (256 * AMP, 256 * AMP))
    img = draw(
        img,
        (x_prev * AMP, y_prev * AMP),
        (x * AMP, y * AMP),
    )
    img = np.hstack([img, frame])
    plt.imsave(OUT_NAME, img[:, :, ::-1])
