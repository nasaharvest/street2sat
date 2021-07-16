import os
import random
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Tuple

import cv2  # type: ignore
import numpy as np
import torch
from google.cloud import firestore, storage  # type: ignore
from ts.torch_handler.base_handler import BaseHandler  # type: ignore
from yolov5.models.common import Detections  # type: ignore
from yolov5.utils.datasets import letterbox  # type: ignore
from yolov5.utils.general import (  # type: ignore
    make_divisible,
    non_max_suppression,
    scale_coords,
)

sys.path.insert(0, "/home/model-server")

from street2sat_utils.client import Prediction
from street2sat_utils.constants import CROP_CLASSES

LABEL_IMG_PERCENT = float(os.environ.get("LABEL_IMG_PERCENT", 1.0))
DEST_BUCKET_NAME = os.environ.get("DEST_BUCKET_NAME", "street2sat-model-predictions")

temp_dir = tempfile.gettempdir()
db = firestore.Client()
storage_client = storage.Client()
dest_bucket = storage_client.get_bucket(DEST_BUCKET_NAME)


class ModelHandler(BaseHandler):
    """
    A custom model handler implementation.
    """

    size = 640
    max_stride = 32
    conf = 0.25
    iou = 0.45
    classes = None
    max_det = 1000

    def initialize(self, context):
        super().initialize(context)
        self.p = next(self.model.parameters())

    @staticmethod
    def download_file(uri: str) -> str:
        """
        Downloads file from Google Cloud Bucket
        """
        uri_as_path = Path(uri)
        bucket_name = uri_as_path.parts[1]
        file_name = "/".join(uri_as_path.parts[2:])
        bucket = storage_client.bucket(bucket_name)
        retries = 3
        blob = bucket.blob(file_name)
        for i in range(retries + 1):
            if blob.exists():
                print(f"HANDLER: Verified {uri} exists.")
                break
            if i == retries:
                raise ValueError(f"HANDLER ERROR: {uri} does not exist.")
            print(
                f"HANDLER: {uri} does not yet exist, sleeping for 5 seconds and trying again."
            )
            time.sleep(5)
        local_path = f"{tempfile.gettempdir()}/{uri_as_path.name}"
        blob.download_to_filename(local_path)
        if not Path(local_path).exists():
            raise FileExistsError(f"HANDLER: {uri} from storage was not downloaded")
        print(f"HANDLER: Verified file downloaded to {local_path}")
        return local_path

    def preprocess_img(self, img: np.ndarray) -> Tuple[List[List[float]], torch.Tensor]:
        s = img.shape[:2]
        g = self.size / max(s)
        shape1 = [[y * g for y in s]]
        shape1 = [
            make_divisible(x, self.max_stride) for x in np.stack(shape1, 0).max(0)
        ]  # inference shape

        x = letterbox(img, new_shape=shape1, auto=False)[0]  # pad
        x = np.ascontiguousarray(x[None].transpose((0, 3, 1, 2)))  # BHWC to BCHW
        img_tensor = (
            torch.from_numpy(x).to(self.p.device).type_as(self.p) / 255.0
        )  # uint8 to fp16/32
        return shape1, img_tensor

    def preprocess(
        self, data
    ) -> Tuple[str, np.ndarray, torch.Tensor, List[List[float]], Dict]:
        print(data)
        print("HANDLER: Starting preprocessing")
        # DOWNLOAD FILE
        try:
            uri: str = next(q["uri"].decode() for q in data if "uri" in q)
        except Exception:
            raise ValueError("'uri' not found.")

        local_path = self.download_file(uri)

        tags = Prediction.generate_tags(open(local_path, "rb"), close=True)
        img = cv2.cvtColor(cv2.imread(local_path), cv2.COLOR_BGR2RGB)
        Path(local_path).unlink()

        shape1, img_tensor = self.preprocess_img(img)

        print("HANDLER: Completed preprocessing")
        return uri, img, img_tensor, shape1, tags

    def inference(self, data, *args, **kwargs) -> Tuple[str, np.ndarray, List, Dict]:
        print("HANDLER: Starting inference")
        uri, img, img_tensor, shape1, tags = data
        y = self.model(img_tensor)[0]
        y = non_max_suppression(
            y, self.conf, iou_thres=self.iou, classes=self.classes, max_det=self.max_det
        )
        scale_coords(shape1, y[0][:, :4], img.shape[:2])
        detections = Detections(
            imgs=[img], pred=y, files=[], times=[0, 1, 2, 3], names=CROP_CLASSES, shape=img_tensor.shape
        )
        results = detections.pandas().xyxy[0].to_dict(orient="records")

        print("HANDLER: Completed inference")
        return uri, img, results, tags

    def postprocess(self, data, *args, **kwargs):
        print("HANDLER: Starting postprocessing")
        uri, img, results, tags = data
        uri_as_path = Path(uri)
        name = "-".join(uri_as_path.parts[2:-1]) + "-" + uri_as_path.stem
        pred = Prediction.from_results_and_tags(
            results=results, tags=tags, name=name, img_np=img
        )
        save_to_db = pred.to_dict()
        save_to_db["input_img"] = uri

        labeled_uri = None
        if random.random() < LABEL_IMG_PERCENT:
            labeled_img = pred.plot_labels()
            local_dest_path = Path(
                tempfile.gettempdir() + f"/result_{uri_as_path.stem}.jpg"
            )
            cv2.imwrite(
                str(local_dest_path), cv2.cvtColor(labeled_img, cv2.COLOR_RGB2BGR)
            )
            labeled_uri = save_to_bucket(uri_as_path, local_dest_path)
            save_to_db["labeled_img"] = labeled_uri

        collection = "street2sat"
        print(f"HANDLER: Saving to collection: {collection}, document: {name}")
        db.collection(collection).document(pred.name).set(save_to_db)

        resp = {"src_uri": uri, "dest_firestore": f"{collection}/{name}"}
        if labeled_uri:
            resp["labeled_uri"] = labeled_uri

        return [resp]


def save_to_bucket(uri_as_path: Path, local_dest_path: Path):
    cloud_dest_parent = "/".join(uri_as_path.parts[2:-1])
    cloud_dest_path_str = f"{cloud_dest_parent}/{local_dest_path.name}"
    dest_blob = dest_bucket.blob(cloud_dest_path_str)
    dest_blob.upload_from_filename(str(local_dest_path))
    print(f"HANDLER: Uploaded to gs://{DEST_BUCKET_NAME}/{cloud_dest_path_str}")
    return f"gs://{DEST_BUCKET_NAME}/{cloud_dest_path_str}"
