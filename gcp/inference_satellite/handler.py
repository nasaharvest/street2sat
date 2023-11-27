import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Tuple

import cv2
import numpy as np
import torch
from google.cloud import firestore, storage  # type: ignore
from pygeotile.tile import Point, Tile
from ts.torch_handler.base_handler import BaseHandler  # type: ignore

sys.path.insert(0, "/home/model-server")

temp_dir = tempfile.gettempdir()

os.environ["LRU_CACHE_CAPACITY"] = "1"

storage_client = storage.Client()
db = firestore.Client()
device = "cuda" if torch.cuda.is_available() else "cpu"

BUCKET_IMGS_W_ARROW = "street2sat-satellite-imgs-with-arrow"
BUCKET_IMGS_W_PRED = "street2sat-satellite-imgs-predictions"
bucket_w_arrow = storage_client.get_bucket(BUCKET_IMGS_W_ARROW)
bucket_w_pred = storage_client.get_bucket(BUCKET_IMGS_W_PRED)

THRESHOLD = 0.5
RADIUS = 5
XYZ_REGEX_PATTERN = r"^.+/\d+/\d+/\d+/.+$"


def gamma_correction(img):
    img = img.astype(float)
    img = (
        255 * (img - np.min(img[:])) / (np.max(img[:]) - np.min(img[:]) + 0.1)
    ).astype(float)
    img = (img + 0.5) / 256
    gamma = -1 / np.nanmean(np.log(img))
    return img ** (gamma)


def get_largest_contour(pred):
    pred_mask = (pred > 0.5).astype(np.uint8)
    contours, _ = cv2.findContours(pred_mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    if len(contours) == 0:
        return pred
    max_contour = max(contours, key=lambda x: cv2.contourArea(x))
    new_img = np.zeros(pred.shape)
    cv2.fillPoly(new_img, pts=[max_contour], color=(1.0, 1.0, 1.0))
    return new_img * pred


def get_new_mark_pos(img):
    x, y = np.where(img > THRESHOLD)
    if len(x) == 0:
        print(f"{len(x)=}")
        return np.unravel_index(np.argmax(img), img.shape)[::-1]
    x_centr, y_centr = np.mean(x), np.mean(y)
    med_val = np.median(img[x, y])
    x_new, y_new = np.where(img >= med_val)
    z = [i for i in zip(x_new, y_new)]
    return min(z, key=lambda k: (x_centr - k[0]) ** 2 + (y_centr - k[1]) ** 2)


def mark_img(img):
    z = np.unravel_index(np.argmax(img), img.shape)[::-1]
    new_img = np.ones((*img.shape, 3)) * img.reshape((*img.shape, 1))
    cv2.circle(new_img, z, RADIUS, (0.0, 1.0, 0.0), -1)
    y1, x1 = get_new_mark_pos(img)
    cv2.circle(new_img, (x1, y1), RADIUS, (0.0, 0.0, 1.0), -1)
    return new_img, x1, y1


class ModelHandler(BaseHandler):
    """
    A custom model handler implementation.
    """

    def preprocess(self, data) -> Tuple[str, torch.Tensor]:
        print(data)
        print("HANDLER: Starting preprocessing")
        try:
            uri: str = next(q["uri"].decode() for q in data if "uri" in q)
        except Exception:
            raise ValueError("'path' not found.")

        path = uri.replace(f"gs://{BUCKET_IMGS_W_ARROW}/", "")

        if not re.match(r"^.+/\d+/\d+/\d+/.+$", path):
            raise ValueError(f"Expecting path: {path} to be <tms>/x/y/z/<img name>")

        blob = bucket_w_arrow.blob(path)
        blob.reload()
        name = blob.metadata["name"]

        # Check that entry is available in firestore
        db_ref = db.document(f"street2sat-v2/{name}")
        if not db_ref.get().exists:
            raise ValueError(f"Not found in firestore: street2sat-v2/{name}")

        local_path = temp_dir + "/" + path.replace("/", "_")
        blob.download_to_filename(local_path)
        img = cv2.imread(local_path)
        Path(local_path).unlink()  # Remove image once read in
        img = img[0:512, 0:512]
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = gamma_correction(img)
        img_tensor = torch.from_numpy(img.transpose(2, 0, 1).astype("float32"))
        img_tensor = img_tensor.to(device)
        return path, img_tensor, db_ref

    def inference(self, data, *args, **kwargs) -> Tuple[str, torch.Tensor]:
        print("HANDLER: Starting inference")
        path, img_tensor, db_ref = data
        pred = self.model(img_tensor.unsqueeze(0))
        pred_numpy = pred.detach().cpu().numpy()[0, 0]
        return path, pred_numpy, db_ref

    def postprocess(self, data, *args, **kwargs):
        print("HANDLER: Starting postprocessing")

        path, pred, db_ref = data
        pred_w_contour = get_largest_contour(pred)
        pred_w_mark, pred_x, pred_y = mark_img(pred_w_contour)

        # TODO: Save only sometimes
        local_path = temp_dir + "/pred_" + path.replace("/", "_")
        cv2.imwrite(local_path, pred_w_mark * 255)
        if not Path(local_path).exists():
            raise FileNotFoundError(f"{local_path} was not found")

        print(f"HANDLER: Saving image: {local_path} to {path}")
        bucket_w_pred.blob(path).upload_from_filename(local_path)
        Path(local_path).unlink()

        # Convert point to new lat/lon,
        # Assumes path is <something>/<x>/<y>/<z>/<something>
        tms, *tile_xyz = path.split("/")
        tile_x, tile_y, tile_z = (int(n) for n in tile_xyz[:3])
        tile = Tile.from_google(tile_x, tile_y, tile_z)
        left_bottom_point, right_top_point = tile.bounds

        # CV2 image has origin (x=0, y=0) at top left
        x1, _ = left_bottom_point.pixels(zoom=tile_z)
        _, y1 = right_top_point.pixels(zoom=tile_z)

        x_on_tile = pred_x // 2
        y_on_tile = pred_y // 2

        point_in_field = Point.from_pixel(x1 + x_on_tile, y1 + y_on_tile, zoom=tile_z)
        coordinate_in_field = point_in_field.latitude_longitude

        resp = {
            f"{tms}_img_source": f"gs://{BUCKET_IMGS_W_ARROW}/{path}",
            f"{tms}_img_segmentation": f"gs://{BUCKET_IMGS_W_PRED}/{path}",
            f"{tms}_field_coord": coordinate_in_field,
            f"{tms}_field_coord_lat": coordinate_in_field[0],
            f"{tms}_field_coord_lon": coordinate_in_field[1],
        }

        # save to db
        db_ref.update(resp)

        return [resp]
