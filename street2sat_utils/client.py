import base64
import io
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from statistics import mean
from typing import IO, Dict, List, Optional, Tuple

import cv2  # type: ignore
import exifread  # type: ignore
import numpy as np
from matplotlib.figure import Figure  # type: ignore
from yolov5 import hubconf  # type: ignore

from street2sat_utils import exif_utils
from street2sat_utils.constants import (
    CROP_CLASSES,
    CROP_TO_HEIGHT_DICT,
    GOPRO_SENSOR_HEIGHT,
    MODEL_PATH,
)


def memoize(f):
    memo = {}

    def helper(x):
        if x not in memo:
            memo[x] = f(x)
        return memo[x]

    return helper


@memoize
def load_model(model_path: str):
    model = hubconf.custom(model_path)
    model.eval()
    return model


@dataclass
class Prediction:
    name: str
    results: List
    time: datetime
    focal_length: int
    coord: Tuple[int, int]
    pixel_height: int
    img: Optional[np.ndarray]
    is_generate_distance: bool

    def __post_init__(self):
        if self.is_generate_distance:
            self.distances = self.generate_distances()

    def to_dict(self):
        skip = ["img", "is_generate_distance"]
        return {k: v for k, v in self.__dict__.items() if k not in skip}

    @staticmethod
    def load_img_from_bytes(img_bytes) -> np.ndarray:
        img_np = np.frombuffer(img_bytes.read(), np.uint8)
        img = cv2.imdecode(img_np, cv2.IMREAD_UNCHANGED)[:, :, ::-1]
        img_bytes.seek(0)
        return img

    @classmethod
    def from_results_and_tags(
        cls, results: List, tags: Dict, name: str, img_bytes=None, img_np=None
    ):
        time = tags["time"]
        focal_length = tags["focal_length"]
        coord = tags["coord"]
        pixel_height = tags["pixel_height"]

        if coord == [None, None]:
            raise ValueError("coord must be set to from_results_and_tags")

        img = None
        if img_bytes is not None:
            img = cls.load_img_from_bytes(img_bytes)
        elif img_np is not None:
            img = img_np

        return cls(
            name=name,
            results=results,
            time=time,
            focal_length=focal_length,
            coord=coord,
            pixel_height=pixel_height,
            img=img,
            is_generate_distance=True,
        )

    @classmethod
    def from_img_bytes(cls, img_bytes: IO, name: str, close=True):
        # Open img
        img = cls.load_img_from_bytes(img_bytes)

        # Extract tags
        tags = cls.generate_tags(img_bytes, close)

        # Predict img
        model = load_model(str(MODEL_PATH))
        raw_results = model(img)
        results = raw_results.pandas().xyxy[0].to_dict(orient="records")

        return cls.from_results_and_tags(results, tags, name, img_np=img)

    @classmethod
    def from_img_path(cls, img_path: str):
        img_bytes = open(img_path, "rb")
        return cls.from_img_bytes(img_bytes, name=img_path)

    @staticmethod
    def generate_tags(img_bytes: IO, close):
        tags = exifread.process_file(img_bytes)
        if close:
            img_bytes.close()
        if tags == {}:
            raise ValueError("Exif tags could not be found for image.")

        return {
            "time": exif_utils.get_exif_datetime(tags),
            "focal_length": exif_utils.get_exif_focal_length(tags),
            "coord": exif_utils.get_exif_location(tags),
            "pixel_height": exif_utils.get_exif_image_height_width(tags)[0],
        }

    def __repr__(self):
        return f"""
Image:
    Time:     {self.time}
    Coord:    {self.coord}
    
Predicted distances:
    {self.distances}
        """

    def get_heights_for_all_crops(self) -> defaultdict:
        heights = defaultdict(list)
        for r in self.results:
            crop_name = CROP_CLASSES[r["class"]]
            height = r["ymax"] - r["ymin"]
            heights[crop_name].append(height)
        return heights

    def generate_distances(self):
        if hasattr(self, "distances"):
            return self.distances

        # Get heights of detected crops
        all_heights = self.get_heights_for_all_crops()

        # Estimate distance to each crop in image
        distances = {
            crop: self.heights_to_distance(heights, crop)
            for crop, heights in all_heights.items()
        }
        return distances

    def heights_to_distance(self, heights: List[int], crop: str):
        distances = [self.get_crop_distance_from_height(h, crop) for h in heights]
        return mean(distances)

    def get_crop_distance_from_height(self, plant_height: int, crop: str) -> float:
        typical_crop_height = CROP_TO_HEIGHT_DICT[crop]
        numerator = self.focal_length * typical_crop_height * self.pixel_height
        denominator = plant_height * GOPRO_SENSOR_HEIGHT
        return (numerator / denominator) / 1000

    @staticmethod
    def img_to_base64_str(img: np.ndarray) -> str:
        s = io.BytesIO()
        fig = Figure()
        ax = fig.subplots()
        ax.imshow(img)
        ax.axis("off")
        fig.savefig(s, format="png")
        return base64.b64encode(s.getbuffer()).decode("ascii")

    def plot_labels(self, to_base_64: bool = False) -> str:
        if self.img is None:
            raise ValueError("self.img must be set to plot_labels")
        img = np.copy(self.img)
        colors = [
            (0, 0, 255),
            (0, 255, 0),
            (255, 0, 0),
            (0, 255, 255),
            (255, 0, 255),
            (255, 255, 0),
        ]
        all_classes_so_far: Dict[int, Tuple[int, int, int]] = {}
        for dt in self.results:
            t, b, l, r, c = [
                int(dt[key]) for key in ["ymax", "ymin", "xmax", "xmin", "class"]
            ]

            if c not in all_classes_so_far:
                all_classes_so_far[c] = colors[len(all_classes_so_far.keys())]

            cv2.rectangle(img, (l, t), (r, b), all_classes_so_far[c], 5)
            cv2.putText(
                img,
                CROP_CLASSES[c],
                (r, b - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                2,
                (0, 0, 0),
                3,
                cv2.LINE_AA,
            )
        if to_base_64:
            return Prediction.img_to_base64_str(img)
        return img

    def compute_bearing(self, closest) -> float:
        lat1 = math.radians(self.coord[0])
        lat2 = math.radians(closest.coord[0])

        diffLong = math.radians(closest.coord[1] - self.coord[1])

        x = math.sin(diffLong) * math.cos(lat2)
        y = math.cos(lat1) * math.sin(lat2) - (
            math.sin(lat1) * math.cos(lat2) * math.cos(diffLong)
        )

        initial_bearing = math.atan2(x, y)
        initial_bearing = math.degrees(initial_bearing)
        compass_bearing = (initial_bearing + 360) % 360

        if closest.time < self.time:
            compass_bearing = (compass_bearing + 180) % 360

        ##### IMPORTANT ASSUMPTION ALL CAMERAS POINT LEFT ####
        return (compass_bearing - 90) % 360

    def set_crop_coord(self, closest) -> None:
        distances = self.generate_distances()
        bearing = self.compute_bearing(closest)

        lat1 = math.radians(self.coord[0])  # Current lat point converted to radians
        lon1 = math.radians(self.coord[1])  # Current long point converted to radians

        self.crop_coord = {}

        for crop, meters in distances.items():
            R = 6378.1  # Radius of the Earth
            brng = math.radians(bearing)  # Bearing is degrees converted to radians.
            d = meters / 1000  # Distance in km

            lat2 = math.asin(
                math.sin(lat1) * math.cos(d / R)
                + math.cos(lat1) * math.sin(d / R) * math.cos(brng)
            )
            lon2 = lon1 + math.atan2(
                math.sin(brng) * math.sin(d / R) * math.cos(lat1),
                math.cos(d / R) - math.sin(lat1) * math.sin(lat2),
            )

            lat2 = math.degrees(lat2)
            lon2 = math.degrees(lon2)

            self.crop_coord[crop] = (lat2, lon2)


def calculate_crop_coords(preds: List[Prediction]) -> List[Prediction]:
    if len(preds) < 2:
        raise ValueError("There must be at least 2 predictions in list.")

    # Sort predictions by date
    sorted_preds = sorted(preds, key=lambda pred: pred.time)

    # The closest predictions for first and last are trivial
    sorted_preds[0].set_crop_coord(closest=sorted_preds[1])
    sorted_preds[-1].set_crop_coord(closest=sorted_preds[-2])

    # Find closest for each remaining prediction
    for i, pred in enumerate(sorted_preds[1:-1]):
        time_to_pred_before = (pred.time - sorted_preds[i - 1].time).total_seconds()
        time_to_pred_after = (pred.time - sorted_preds[i + 1].time).total_seconds()
        if time_to_pred_before < time_to_pred_after:
            pred.set_crop_coord(closest=sorted_preds[i - 1])
        else:
            pred.set_crop_coord(closest=sorted_preds[i + 1])

    return sorted_preds
