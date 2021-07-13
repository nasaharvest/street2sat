import base64
import io
import math
import os
from statistics import mean
from typing import Dict, List, Tuple, Union

import cv2  # type: ignore
import numpy as np
import torch
from matplotlib.figure import Figure  # type: ignore
from yolov5 import hubconf  # type: ignore
from yolov5.models.yolo import Model  # type: ignore


def predict(images: List[np.ndarray]) -> List[str]:
    torch.set_num_threads(1)
    model = get_model()
    all_results = []
    with torch.no_grad():
        for img in images:
            all_results.append(run_prediction(img, model))
    return all_results


def run_prediction(img: np.ndarray, model: Model) -> str:
    results = model(img)
    results = results.pandas().xyxy[0].to_json(orient="records")
    return results


def get_model(path: str = "street2sat_utils/model_weights/best.pt") -> Model:
    assert os.path.exists(path), "Model path does not exist!"
    model = hubconf.custom(path)
    model.eval()
    return model


def get_image(image_path: str) -> str:
    img = cv2.imread(image_path)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    s = io.BytesIO()
    fig = Figure()
    ax = fig.subplots()
    ax.imshow(img)
    ax.axis("off")
    fig.savefig(s, format="png")
    return base64.b64encode(s.getbuffer()).decode("ascii")


def plot_labels(
    img: np.ndarray,
    results: List[Dict[str, float]],
    path_prefix: str = "street2sat_utils/crop_info/",
) -> str:
    classes = {}
    with open(os.path.join(path_prefix, "classes.txt")) as classes_file:
        for i, line in enumerate(classes_file):
            classes[i] = line.strip()

    img = np.copy(img)
    colors = [
        (0, 0, 255),
        (0, 255, 0),
        (255, 0, 0),
        (0, 255, 255),
        (255, 0, 255),
        (255, 255, 0),
    ]
    all_classes_so_far: Dict[int, Tuple[int, int, int]] = {}
    for dt in results:
        t = int(dt["ymax"])
        b = int(dt["ymin"])
        l = int(dt["xmax"])
        r = int(dt["xmin"])
        c = int(dt["class"])

        if c not in all_classes_so_far:
            all_classes_so_far[c] = colors[len(all_classes_so_far.keys())]

        cv2.rectangle(img, (l, t), (r, b), all_classes_so_far[c], 5)
        cv2.putText(
            img,
            classes[c],
            (r, b - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            2,
            (0, 0, 0),
            3,
            cv2.LINE_AA,
        )

    s = io.BytesIO()
    fig = Figure()
    ax = fig.subplots()
    ax.imshow(img)
    ax.axis("off")
    fig.savefig(s, format="png")
    return base64.b64encode(s.getbuffer()).decode("ascii")


def get_height_pixels(
    outputs: List[Dict[str, Union[int, float]]]
) -> Dict[int, List[float]]:
    all_h: Dict[int, List[float]] = {}
    for dt in outputs:
        class_name = dt["class"]
        if not isinstance(class_name, int):
            raise ValueError(f"class should be an integer but got {class_name}")

        ymax = dt["ymax"]
        ymin = dt["ymin"]

        if class_name in all_h.keys():
            all_h[class_name].append(ymax - ymin)
        else:
            all_h[class_name] = [ymax - ymin]

    return all_h


def get_distance_meters(
    outputs: List[Dict[str, Union[int, float]]],
    focal_length: float,
    pixel_height: float,
    path_prefix: str = "street2sat_utils/crop_info/",
) -> Dict[str, str]:
    GOPRO_SENSOR_HEIGHT = 4.55

    heights = {}
    with open(os.path.join(path_prefix, "heights.txt")) as heights_file:
        for line in heights_file:
            heights[line.split()[0]] = float(line.split()[1])
    classes = {}
    with open(os.path.join(path_prefix, "classes.txt")) as classes_file:
        for i, line in enumerate(classes_file):
            classes[i] = line.strip()

    detected_heights = get_height_pixels(outputs)

    dict_info = {}
    for crop_index in detected_heights.keys():
        crop_name = classes[crop_index]
        typical_crop_height = heights[crop_name]
        all_dist = []
        for plant_height in detected_heights[crop_index]:
            dist = (focal_length * typical_crop_height * pixel_height) / (
                plant_height * GOPRO_SENSOR_HEIGHT
            )
            dist = dist / 1000
            all_dist.append(dist)
        dict_info[crop_name] = str(round(mean(all_dist), 3)) + " meters"
    return dict_info


def point_meters_away(
    original_coord: Tuple[float, float], heading: float, meters_dict: Dict[str, str]
) -> Dict[str, Tuple[float, float]]:
    # https://stackoverflow.com/a/7835325
    new_p_dict = {}
    for crop, meters_str in meters_dict.items():
        R = 6378.1  # Radius of the Earth
        brng = math.radians(heading)  # Bearing is degrees converted to radians.
        meters = float(meters_str.split(" ")[0])
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


def get_new_points(time_dict: Dict, coord_dict: Dict, distance_dict: Dict) -> Tuple:
    # find closest point in time
    # find heading by doing coordinate at closest point and current point 90 degrees left
    # add distance to current point
    # taken from https://gist.github.com/jeromer/2005586
    bearings = {}
    for time_val, file in time_dict.items():
        all_times = list(time_dict.keys())
        all_times.remove(time_val)
        # closest_time = min(all_times, key=lambda d: abs(time.mktime(d) - time.mktime(time_val)))
        closest_time = min(all_times, key=lambda d: (d - time_val).total_seconds())

        file_with_closest_time = time_dict[closest_time]
        original_coord = coord_dict[file]
        closest_coord = coord_dict[file_with_closest_time]

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

        if closest_time < time_val:
            compass_bearing = (compass_bearing + 180) % 360

        ##### IMPORTANT ASSUMPTION ALL CAMERAS POINT LEFT ####
        bearings[file] = (compass_bearing - 90) % 360

    # file:crop:(lat,long)
    new_points = {}
    for file, bearing in bearings.items():
        if file in distance_dict.keys():
            distance_meters = distance_dict[file]
            translated_coords = point_meters_away(
                coord_dict[file], bearing, distance_meters
            )
            new_points[file] = translated_coords

    return bearings, new_points


if __name__ == "__main__":
    model = get_model("../street2sat_utils/model_weights/best.pt")
    img1_path = "../example_images/GP__1312.JPG"
    img1 = cv2.cvtColor(cv2.imread(img1_path), cv2.COLOR_BGR2RGB)
    run_prediction(img1, model)
    # predict('../temp/uQBYaAsIgV/')
