import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Tuple

import cv2  # type: ignore
import exifread
import matplotlib.pyplot as plt
import torch
from google.cloud import firestore, storage  # type: ignore
from ts.torch_handler.base_handler import BaseHandler  # type: ignore

sys.path.insert(0, "/home/model-server")

from inference_utils import download_file, get_name_from_uri  # noqa: E402

os.environ["LRU_CACHE_CAPACITY"] = "1"

storage_client = storage.Client()
db = firestore.Client()
DEST_BUCKET_NAME = os.environ.get("DEST_BUCKET_NAME", "street2sat-crops")
device = "cuda" if torch.cuda.is_available() else "cpu"


def _get_if_exist(data, key):
    if key in data:
        return data[key]
    return None


def _convert_to_degress(value):
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

    lat = _convert_to_degress(gps_latitude)
    if gps_latitude_ref.values[0] != "N":
        lat = 0 - lat

    lon = _convert_to_degress(gps_longitude)
    if gps_longitude_ref.values[0] != "E":
        lon = 0 - lon

    return lat, lon


def get_exif_datetime(exif_data):
    date_time = _get_if_exist(exif_data, "Image DateTime")
    dt = datetime.strptime(str(date_time), "%Y:%m:%d %H:%M:%S")
    return dt


def get_exif_focal_length(exif_data):
    n = _get_if_exist(exif_data, "EXIF FocalLength")
    return n.values[0].num


def get_exif_image_height_width(exif_data):
    w = _get_if_exist(exif_data, "EXIF ExifImageWidth")
    h = _get_if_exist(exif_data, "EXIF ExifImageLength")
    return h.values[0], w.values[0]


class ModelHandler(BaseHandler):
    """
    A custom model handler implementation.
    """

    def preprocess(self, data) -> Tuple[str, torch.Tensor, dict]:
        print(data)
        print("HANDLER: Starting preprocessing")
        try:
            uri: str = next(q["uri"].decode() for q in data if "uri" in q)
        except Exception:
            raise ValueError("'uri' not found.")

        local_path = download_file(storage_client, uri)

        img_bytes = open(local_path, "rb")
        tags = exifread.process_file(img_bytes)
        img_bytes.close()
        img_tags = {}
        if tags != {}:
            img_tags = {
                "time": get_exif_datetime(tags),
                "focal_length": get_exif_focal_length(tags),
                "coord": get_exif_location(tags),
                "pixel_height": get_exif_image_height_width(tags)[0],
            }

        img = plt.imread(local_path)
        Path(local_path).unlink()
        img = cv2.resize(img, (300, 300)) / 255
        img = img.transpose(2, 0, 1).astype("float32")
        img_tensor = torch.from_numpy(img).float().to(device)
        return uri, img_tensor, img_tags

    def inference(self, data, *args, **kwargs) -> Tuple[str, bool, dict]:
        print("HANDLER: Starting inference")
        uri, img_tensor, img_tags = data
        output = self.model(img_tensor.unsqueeze(0))
        is_crop = (output <= 0).item()
        print(f"HANDLER: is_crop {is_crop}")
        return uri, is_crop, img_tags

    def postprocess(self, data, *args, **kwargs):
        print("HANDLER: Starting postprocessing")
        uri, is_crop, img_tags = data
        resp = {"is_crop": is_crop, "uri": uri}

        name = get_name_from_uri(uri)
        save_to_db = {
            "input_img": uri,
            "name": name,
            "is_crop": is_crop,
            **img_tags,
        }
        save_to_db["results"] = None

        collection = "street2sat-v2"
        print(f"HANDLER: Adding to collection: {collection}, document: {name}")
        db.collection(collection).document(name).set(save_to_db)

        resp = {
            "input_img": uri,
            "name": name,
            "is_crop": is_crop,
        }
        if not is_crop:
            return [resp]

        uri_as_path = Path(uri)
        src_bucket_name = uri_as_path.parts[1]
        src_bucket = storage_client.get_bucket(src_bucket_name)
        blob_name = "/".join(uri_as_path.parts[2:])
        src_blob = src_bucket.blob(blob_name)

        dest_bucket = storage_client.get_bucket(DEST_BUCKET_NAME)
        src_bucket.copy_blob(src_blob, dest_bucket, blob_name)
        resp["dest_uri"] = f"gs://{DEST_BUCKET_NAME}/{blob_name}"

        return [resp]
