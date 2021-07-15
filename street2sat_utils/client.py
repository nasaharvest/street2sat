import base64
import io
import json
import math
from collections import Counter, defaultdict
from statistics import mean
from typing import Dict, List, Optional, Tuple, Union

import cv2  # type: ignore
import exifread  # type: ignore
import numpy as np
from matplotlib.figure import Figure  # type: ignore
from yolov5 import hubconf  # type: ignore
from yolov5.models.yolo import Model  # type: ignore

from constants import CROP_CLASSES, CROP_TO_HEIGHT_DICT, GOPRO_SENSOR_HEIGHT, MODEL_PATH
from street2sat_utils import exif_utils

model: Model = hubconf.custom(str(MODEL_PATH))
model.eval()


class Prediction:
    def __init__(
        self,
        img_path: Optional[str] = None,
        img_bytes: Optional[io.BytesIO] = None,
        already_generated_results_str: Optional[str] = None,
        already_generated_tags: Optional[Dict] = None,
        name: Optional[str] = None,
    ):

        if name:
            self.name = name

        if img_path is None and img_bytes is None:
            raise ValueError("One of img_path, img_bytes, must be set.")

        elif img_path:
            img_bytes = open(img_path, "rb")
            self.img = cv2.cvtColor(cv2.imread(img_path), cv2.COLOR_BGR2RGB)

        elif img_bytes:
            img_np = np.frombuffer(img_bytes.read(), np.uint8)
            self.img = cv2.imdecode(img_np, cv2.IMREAD_UNCHANGED)[:, :, ::-1]
            img_bytes.seek(0)

        # Load tags
        if already_generated_tags:
            self.time = already_generated_tags["taken_time"]
            self.focal_length = already_generated_tags["focal_length"]
            self.coord = already_generated_tags["lat_long"]
            self.pixel_height = already_generated_tags["pixel_height"]
            self.pixel_width = already_generated_tags["pixel_width"]
        else:
            tags = exifread.process_file(img_bytes)
            self.time = exif_utils.get_exif_datetime(tags)
            self.focal_length = exif_utils.get_exif_focal_length(tags)
            self.coord = exif_utils.get_exif_location(tags)
            (
                self.pixel_height,
                self.pixel_width,
            ) = exif_utils.get_exif_image_height_width(tags)

        # Predict img
        if already_generated_results_str:
            self.results_str = already_generated_results_str
            self.results = json.loads(self.results_str)
        else:
            raw_results = model(self.img)
            self.results = raw_results.pandas().xyxy[0].to_dict(orient="records")
            self.results_str = raw_results.pandas().xyxy[0].to_json(orient="records")

        self.crop_count = Counter([CROP_CLASSES[r["class"]] for r in self.results])

        # Get heights of detected crops
        all_heights = self.get_heights_for_all_crops(self.results)

        # Estimate distance to each crop in image
        self.distances = {
            crop: self.heights_to_distance(crop, heights)
            for crop, heights in all_heights.items()
        }

    def __repr__(self):
        return f"""
Image:
    Time:     {self.time}
    Coord:    {self.coord}
    Dims:     {self.pixel_height} x {self.pixel_width} 
    
Predictions:
    {self.crop_count}
    
Predicted distances:
    {self.distances}
        """

    @staticmethod
    def get_heights_for_all_crops(results):
        heights = defaultdict(list)
        for r in results:
            crop_name = CROP_CLASSES[r["class"]]
            height = r["ymax"] - r["ymin"]
            heights[crop_name].append(height)
        return heights

    def heights_to_distance(self, crop, heights):
        distances = [self.get_crop_distance_from_height(crop, h) for h in heights]
        return mean(distances)

    def get_crop_distance_from_height(self, crop, plant_height):
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
            return self.img_to_base64_str(img)
        return img


def point_meters_away(
    original_coord: Tuple[float, float], heading: float, meters_dict: Dict[str, str]
) -> Dict[str, Tuple[float, float]]:
    # https://stackoverflow.com/a/7835325
    new_p_dict = {}
    for crop, meters in meters_dict.items():
        R = 6378.1  # Radius of the Earth
        brng = math.radians(heading)  # Bearing is degrees converted to radians.
        # meters = float(meters_str.split(" ")[0])
        d = meters / 1000  # Distance in km

        lat1 = math.radians(original_coord[0])  # Current lat point converted to radians
        lon1 = math.radians(
            original_coord[1]
        )  # Current long point converted to radians

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

        new_p_dict[crop] = (lat2, lon2)

    return new_p_dict


def get_new_points2(preds: List[Prediction]):

    # Sort predictions by date
    sorted_preds = sorted(preds, key=lambda pred: pred.time)

    # Go through predictions for each prediction find closest other prediction
    for i, pred in enumerate(sorted_preds):
        pred_before = sorted_preds[i - 1] if i > 0 else None
        pred_after = sorted_preds[i + 1] if (i + 1) < len(preds) else None

        if pred_before and pred_after:
            time_to_pred_before = (pred.time - pred_before.time).total_seconds()
            time_to_pred_after = (pred.time - sorted_preds[i + 1].time).total_seconds()
            if time_to_pred_before < time_to_pred_after:
                closest_pred = pred_before
            else:
                closest_pred = pred_after
        elif pred_before:
            closest_pred = pred_before
        elif pred_after:
            closest_pred = pred_after
        else:
            raise ValueError(
                "A predictions list with atleast two elements must be passed."
            )

        # Go through each prediction pair and get the latitude from both to calculate bearing
        closest_is_earlier = closest_pred == pred_before
        pred.bearing = compute_bearing(
            pred.coord, closest_pred.coord, closest_is_earlier
        )
        pred.crop_coord = point_meters_away(pred.coord, pred.bearing, pred.distances)


def compute_bearing(original_coord, closest_coord, closest_is_earlier):
    lat1 = math.radians(original_coord[0])
    lat2 = math.radians(closest_coord[0])

    diffLong = math.radians(closest_coord[1] - original_coord[1])

    x = math.sin(diffLong) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - (
        math.sin(lat1) * math.cos(lat2) * math.cos(diffLong)
    )

    initial_bearing = math.atan2(x, y)
    initial_bearing = math.degrees(initial_bearing)
    compass_bearing = (initial_bearing + 360) % 360

    if closest_is_earlier:
        compass_bearing = (compass_bearing + 180) % 360

    ##### IMPORTANT ASSUMPTION ALL CAMERAS POINT LEFT ####
    return (compass_bearing - 90) % 360
