import cv2
import os
import tempfile
import wget
from datetime import timedelta
from pygeotile.tile import Tile, Point
from pathlib import Path
from google.cloud import storage, firestore
from google.cloud.firestore_v1.base_query import FieldFilter

# Google Cloud Storage
storage_client = storage.Client()
bucket_imgs = storage_client.get_bucket("street2sat-satellite-imgs")
bucket_imgs_w_arrow = storage_client.get_bucket("street2sat-satellite-imgs-with-arrow")

# Tile servers
ZOOM = 18
MAP_TILE_SERVERS = os.environ.get("MAP_TILE_SERVERS", "mapbox bing").lower()
MAPBOX_URL = "https://api.mapbox.com/styles/v1/mapbox/satellite-v9/tiles/256"
BING_URL = "http://ecn.t0.tiles.virtualearth.net/tiles"

if "mapbox" in MAP_TILE_SERVERS:
    from google.cloud import secretmanager

    secret_client = secretmanager.SecretManagerServiceClient()
    name = f"projects/1012768714927/secrets/MAPBOX_TOKEN_IVAN/versions/1"
    response = secret_client.access_secret_version(name=name)
    MAPBOX_TOKEN = response.payload.data.decode("UTF-8")
else:
    MAPBOX_TOKEN = ""

# Firestore
db = firestore.Client()
coll = db.collection("street2sat-v2")

# Processing settings
AMP = 2
LEFT_DRIVE_COUNTRIES = [
    "Botswana",
    "Kenya",
    "Lesotho",
    "Malawi",
    "Mauritius",
    "Mozambique",
    "Namibia",
    "South Africa",
    "Swaziland",
    "Tanzania",
    "Uganda",
    "Saint Helena",
    "Seychelles",
    "Zambia",
    "Zimbabwe",
]

temp_dir = tempfile.gettempdir()


def get_orthogonal(prev_pos, curr_pos, amp=3, flip=False):
    """
    Finds a point to the left (or right if flipped) based on
    current and previous position. Amp is a scaling factor
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


def get_xy(lat, lon):
    pixel_x, pixel_y = Point(lat, lon).pixels(ZOOM)
    tile_xy = pixel_x // 256, pixel_y // 256
    within_tile_xy = (pixel_x % 256) * AMP, (pixel_y % 256) * AMP
    return tile_xy, within_tile_xy


def draw_arrow(img, prev_pixel_xy, pixel_xy, flip=False):
    img = cv2.resize(img, (256 * AMP, 256 * AMP))
    img = cv2.circle(img, prev_pixel_xy, 1, (0, 0, 255), -1)
    img = cv2.circle(img, pixel_xy, 1, (255, 0, 0), -1)
    img = cv2.arrowedLine(img, prev_pixel_xy, pixel_xy, (0, 255, 0), 1)
    orth_xy = get_orthogonal(prev_pixel_xy, pixel_xy, flip=flip)
    img = cv2.arrowedLine(img, pixel_xy, orth_xy, (51, 255, 255), 1)
    return img


def compute_and_draw_arrow(img_path, doc, img_w_arrow_path):
    img = cv2.imread(img_path, cv2.IMREAD_COLOR)

    lat, lon = doc["coord"]
    origin_time = doc["time"]
    start_time = origin_time - timedelta(seconds=10)
    tile_xy, pixel_xy = get_xy(lat, lon)

    photo_references = (
        coll.where(filter=FieldFilter("time", ">", start_time))
        .where(filter=FieldFilter("time", "<=", origin_time))
        .order_by("time", direction="DESCENDING")
        .limit(5)
        .get()
    )

    is_left_hand_country = any(
        c.lower() in doc["name"].lower() for c in LEFT_DRIVE_COUNTRIES
    )

    for photo_ref in photo_references:
        if photo_ref.id == doc["name"]:
            continue
        prev_lat, prev_lon = photo_ref.to_dict()["coord"]
        prev_tile_xy, prev_pixel_xy = get_xy(prev_lat, prev_lon)
        if tile_xy == prev_tile_xy:
            img_w_arrow = draw_arrow(img, prev_pixel_xy, pixel_xy, is_left_hand_country)
            cv2.imwrite(img_w_arrow_path, img_w_arrow)
            return img_w_arrow

    # TODO if not found use photo_references after
    raise ValueError(f"No photo found before to establish direction for {doc['name']}")


def hello_world(request):
    request_json = request.get_json(silent=True)
    for key in ["name"]:
        if key not in request_json:
            raise ValueError(f"{key} not found in request_json")

    name = request_json["name"]
    zoom = request_json.get("zoom", ZOOM)

    # Get database entry
    docref = db.document(f"street2sat-v2/{name}")
    doc = docref.get().to_dict()
    lat, lon = doc["coord"]

    t = Tile.for_latitude_longitude(lat, lon, zoom)

    endpoints = {
        "mapbox": f"{MAPBOX_URL}/{zoom}/{t.google[0]}/{t.google[1]}?access_token={MAPBOX_TOKEN}",
        "bing": f"{BING_URL}/a{t.quad_tree}.jpeg?g=14009",
    }

    response = {}

    for map_tile_server in MAP_TILE_SERVERS.split(" "):
        try:
            blob = bucket_imgs.blob(
                f"{map_tile_server}/{t.google[0]}/{t.google[1]}/{zoom}.jpg"
            )
            img_path = f"{temp_dir}/{map_tile_server}_{name}.jpg"

            # Download satellite image
            if not blob.exists():
                print(f"Fetching from: {endpoints[map_tile_server]}")
                wget.download(endpoints[map_tile_server], img_path)
                # Upload satellite image
                blob.upload_from_filename(img_path)
                blob.metadata = request_json
                blob.patch()
                response[f"{map_tile_server}_fetched_img"] = True
            else:
                blob.download_to_filename(img_path)
                response[f"{map_tile_server}_fetched_img"] = False
            response[f"{map_tile_server}_img"] = blob.name
        except Exception as e:
            print(e)
            response[f"{map_tile_server}_fetched_img"] = False
            continue

        try:
            blob_w_arrow = bucket_imgs_w_arrow.blob(
                f"{map_tile_server}/{t.google[0]}/{t.google[1]}/{zoom}/{name}.jpg"
            )

            # Add arrow
            img_w_arrow_path = f"{temp_dir}/{map_tile_server}_arrow_{name}.jpg"
            compute_and_draw_arrow(img_path, doc, img_w_arrow_path)
            blob_w_arrow.upload_from_filename(img_w_arrow_path)
            blob_w_arrow.metadata = request_json
            blob_w_arrow.patch()
            response[f"{map_tile_server}_added_arrow"] = True

        except Exception as e:
            print(e)
            response[f"{map_tile_server}_added_arrow"] = False

        Path(img_path).unlink(missing_ok=True)
        Path(img_w_arrow_path).unlink(missing_ok=True)

    return response


# TODO: Delete images from tempdir

if __name__ == "__main__":
    request_json = {
        "name": "Uganda_v2-1829244-2020-06-24_Edrick_2-2020-06-24_Edrick_2-124GOPRO-G0181192"
    }

    class MockRequest:
        def get_json(silent):
            return request_json

    response = hello_world(MockRequest)
    print(response)
