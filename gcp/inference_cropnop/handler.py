import os
import sys
from pathlib import Path
from typing import Tuple

import cv2  # type: ignore
import exifread
import matplotlib.pyplot as plt
import torch

from google.cloud import storage, firestore  # type: ignore
from ts.torch_handler.base_handler import BaseHandler  # type: ignore

sys.path.insert(0, "/home/model-server")

from inference_utils import download_file, get_name_from_uri
from street2sat_utils import exif_utils

os.environ["LRU_CACHE_CAPACITY"] = "1"

storage_client = storage.Client()
db = firestore.Client()
DEST_BUCKET_NAME = os.environ.get("DEST_BUCKET_NAME", "street2sat-crops")
device = ("cuda" if torch.cuda.is_available() else "cpu")

class ModelHandler(BaseHandler):
    """
    A custom model handler implementation.
    """

    def preprocess(
        self, data
    ) -> Tuple[str, torch.Tensor]:
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
                "time": exif_utils.get_exif_datetime(tags),
                "focal_length": exif_utils.get_exif_focal_length(tags),
                "coord": exif_utils.get_exif_location(tags),
                "pixel_height": exif_utils.get_exif_image_height_width(tags)[0],
            }

        img = plt.imread(local_path)
        Path(local_path).unlink()
        img = cv2.resize(img, (300,300)) / 255
        img = img.transpose(2,0,1).astype('float32')
        img_tensor = torch.from_numpy(img).float().to(device)
        return uri, img_tensor, img_tags
        

    def inference(self, data, *args, **kwargs) -> Tuple[str, torch.Tensor]:
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