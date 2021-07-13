import tempfile
import time
from pathlib import Path
from typing import List, Tuple

import cv2  # type: ignore
import numpy as np
import torch
from google.cloud import storage  # type: ignore
from ts.torch_handler.base_handler import BaseHandler  # type: ignore
from yolov5.models.common import Detections  # type: ignore
from yolov5.utils.datasets import letterbox  # type: ignore
from yolov5.utils.general import (  # type: ignore
    make_divisible,
    non_max_suppression,
    scale_coords,
)

temp_dir = tempfile.gettempdir()

storage_client = storage.Client()
dest_bucket_name = "street2sat-model-predictions"
dest_bucket = storage_client.get_bucket(dest_bucket_name)


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
    names = [
        "tobacco",
        "coffee",
        "banana",
        "tea",
        "beans",
        "maize",
        "sorghum",
        "millet",
        "sweet_potatoes",
        "cassava",
        "rice",
        "sugarcane",
    ]

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

    def preprocess(
        self, data
    ) -> Tuple[str, np.ndarray, torch.Tensor, List[List[float]]]:
        print(data)
        print("HANDLER: Starting preprocessing")
        # DOWNLOAD FILE
        try:
            uri: str = next(q["uri"].decode() for q in data if "uri" in q)
        except Exception:
            raise ValueError("'uri' not found.")

        local_path = self.download_file(uri)

        img: np.ndarray = cv2.cvtColor(cv2.imread(local_path), cv2.COLOR_BGR2RGB)
        Path(local_path).unlink()

        # PREPROCESS IMAGE
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

        print("HANDLER: Completed preprocessing")
        return uri, img, img_tensor, shape1

    def inference(
        self, data, *args, **kwargs
    ) -> Tuple[str, np.ndarray, torch.Tensor, List, torch.Tensor]:
        print("HANDLER: Starting inference")
        uri, img, img_tensor, shape1 = data
        y = self.model(img_tensor)[0]
        print("HANDLER: Completed inference")
        return uri, img, img_tensor, shape1, y

    def postprocess(self, data, *args, **kwargs):
        print("HANDLER: Starting postprocessing")
        uri, img, img_tensor, shape1, y = data

        y = non_max_suppression(
            y, self.conf, iou_thres=self.iou, classes=self.classes, max_det=self.max_det
        )  # NMS
        scale_coords(shape1, y[0][:, :4], img.shape[:2])
        detections = Detections(
            [img], y, ["test.jpg"], [0, 1, 2, 3], self.names, img_tensor.shape
        )

        uri_as_path = Path(uri)

        local_dest_path = Path(
            tempfile.gettempdir() + f"/result_{uri_as_path.stem}.json"
        )
        detections.pandas().xyxy[0].to_json(
            path_or_buf=str(local_dest_path), indent=4, orient="records"
        )

        cloud_dest_parent = "/".join(uri_as_path.parts[2:-1])
        cloud_dest_path_str = f"{cloud_dest_parent}/{local_dest_path.name}"
        dest_blob = dest_bucket.blob(cloud_dest_path_str)
        dest_blob.upload_from_filename(str(local_dest_path))
        print(f"HANDLER: Uploaded to gs://{dest_bucket_name}/{cloud_dest_path_str}")
        return [
            {
                "src_uri": uri,
                "dest_uri": f"gs://{dest_bucket_name}/{cloud_dest_path_str}",
            }
        ]
