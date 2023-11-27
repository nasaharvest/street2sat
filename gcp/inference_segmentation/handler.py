import os
import random
import sys
import tempfile
from pathlib import Path
from typing import Tuple

import matplotlib.pyplot as plt
import numpy as np  # type: ignore
import torch
from google.cloud import firestore, storage  # type: ignore
from skimage.io import imread
from skimage.transform import resize
from ts.torch_handler.base_handler import BaseHandler  # type: ignore

sys.path.insert(0, "/home/model-server")

from inference_utils import download_file, get_name_from_uri  # noqa: E402

os.environ["LRU_CACHE_CAPACITY"] = "1"
storage_client = storage.Client()
db = firestore.Client()
DEST_BUCKET_NAME = os.environ.get("DEST_BUCKET_NAME", "street2sat-segmentations")
dest_bucket = storage_client.get_bucket(DEST_BUCKET_NAME)
CLASSES = [
    "background",
    "banana",
    "maize",
    "rice",
    "soybean",
    "sugarcane",
    "sunflower",
    "tobacco",
    "wheat",
]
device = "cuda" if torch.cuda.is_available() else "cpu"


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
            raise ValueError("'uri' not found.")

        local_path = download_file(storage_client, uri)

        img = imread(local_path)
        Path(local_path).unlink()
        img = resize(img, (800, 800))
        img = img.astype(float)
        img = (
            255 * (img - np.min(img[:])) / (np.max(img[:]) - np.min(img[:]) + 0.1)
        ).astype(float)
        img = (img + 0.5) / 256
        gamma = -1 / np.nanmean(np.log(img))
        img = img ** (gamma)
        img = img.transpose(2, 0, 1).astype("float32")
        img_tensor = torch.from_numpy(img).unsqueeze(0).to(device)

        return uri, img_tensor

    def inference(self, data, *args, **kwargs) -> Tuple[str, torch.Tensor]:
        print("HANDLER: Starting inference")
        uri, img_tensor = data
        output = self.model(img_tensor)[0].cpu().detach().numpy()
        return uri, output

    def postprocess(self, data, *args, **kwargs):
        print("HANDLER: Starting postprocessing")
        uri, output = data

        save_segmentation_images = random.random() < 0.01

        results = {}
        image_size = output.shape[1] * output.shape[2]

        files_to_upload = []
        for i, crop in enumerate(CLASSES):
            results[crop] = round(output[i].sum() / image_size, 4)
            print(f"HANDLER: Segmentation {crop}: {results[crop]}")
            if save_segmentation_images:
                file_name = Path(tempfile.gettempdir()) / f"{crop}.png"
                plt.imsave(file_name, output[i], cmap=plt.cm.gray)
                files_to_upload.append(file_name)

        uploaded_files_uri = []
        uri_as_path = Path(uri)
        if save_segmentation_images:
            for i, file_name in enumerate(files_to_upload):
                print(
                    f"HANDLER: Uploading segmentation image {i+1}/{len(files_to_upload)}"
                )
                segment_uri = save_to_bucket(uri_as_path, file_name)
                uploaded_files_uri.append(segment_uri)
                file_name.unlink()

        # Save result to firestore db
        name = get_name_from_uri(uri)
        save_to_db = {"results": results}
        if save_segmentation_images:
            save_to_db["segmentation_images"] = uploaded_files_uri

        collection = "street2sat-v2"
        print(f"HANDLER: Updating collection: {collection}, document: {name}")
        db.collection(collection).document(name).update(save_to_db)

        return [
            {
                "input_img": uri,
                "name": name,
                "results": results,
            }
        ]


def save_to_bucket(uri_as_path: Path, local_dest_path: Path):
    cloud_dest_parent = "/".join(uri_as_path.parts[2:-1])
    cloud_dest_path_str = (
        f"{cloud_dest_parent}/{uri_as_path.stem}/{local_dest_path.name}"
    )
    dest_blob = dest_bucket.blob(cloud_dest_path_str)
    dest_blob.upload_from_filename(str(local_dest_path))
    print(f"HANDLER: Uploaded to gs://{DEST_BUCKET_NAME}/{cloud_dest_path_str}")
    return f"gs://{DEST_BUCKET_NAME}/{cloud_dest_path_str}"
