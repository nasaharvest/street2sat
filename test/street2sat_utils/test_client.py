import numpy as np
from datetime import datetime
from pathlib import Path
from unittest import TestCase, mock
from yolov5.models.yolo import AutoShape

from street2sat_utils.client import (
    predict,
    run_prediction,
    get_model,
    get_image,
    plot_labels,
    get_height_pixels,
    get_distance_meters,
    point_meters_away,
    get_new_points,
)

home_dir = Path(__file__).parent.parent.parent


class TestClient(TestCase):

    sample_results = [
        {
            "xmin": 474.7214355469,
            "ymin": 834.8707885742,
            "xmax": 646.2578735352,
            "ymax": 1155.9974365234,
            "confidence": 0.6548386812,
            "class": 11,
            "name": "sugarcane",
        },
        {
            "xmin": 1242.162109375,
            "ymin": 750.7573852539,
            "xmax": 1398.0832519531,
            "ymax": 1085.2777099609,
            "confidence": 0.6288382411,
            "class": 11,
            "name": "sugarcane",
        },
        {
            "xmin": 1986.4957275391,
            "ymin": 783.6393432617,
            "xmax": 2100.9672851562,
            "ymax": 1043.1098632812,
            "confidence": 0.6045597196,
            "class": 11,
            "name": "sugarcane",
        },
    ]

    @mock.patch("street2sat_utils.client.get_model")
    def test_predict_no_imgs(self, mock_get_model):
        test_images = []
        results = predict(test_images)
        mock_get_model.assert_called_once()
        self.assertEqual(results, [])

    @mock.patch("street2sat_utils.client.run_prediction")
    @mock.patch("street2sat_utils.client.get_model")
    def test_predict_one_imgs(self, mock_get_model, mock_run_prediction):
        test_images = [np.ones((3, 64, 64))]
        mock_return = "{json: string}"
        mock_run_prediction.return_value = mock_return
        results = predict(test_images)
        mock_get_model.assert_called_once()
        mock_run_prediction.assert_called_once()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], mock_return)

    @mock.patch("yolov5.models.common.Detections")
    @mock.patch("yolov5.models.yolo.Model")
    def test_run_prediction(self, mock_Model, mock_Detections):
        mock_Model.return_value = mock_Detections
        res = run_prediction(np.ones((3, 64, 64)), mock_Model)
        self.assertEqual(res, mock_Detections.pandas().xyxy[0].to_json())

    def test_get_model(self):
        model_path = home_dir / "street2sat_utils/model_weights/best.pt"
        m = get_model(str(model_path))
        self.assertFalse(m.training)
        self.assertEqual(type(m), AutoShape)

    def test_get_image(self):
        image_path = home_dir / "example_images/GP__1312.JPG"
        img = get_image(str(image_path))
        self.assertEqual(type(img), str)
        self.assertEqual(len(img), 347596)

    def test_plot_labels(self):
        test_img = np.ones((2000, 2000, 3))
        path_prefix = home_dir / "street2sat_utils/crop_info"
        img_result = plot_labels(test_img, self.sample_results[:1], path_prefix)
        self.assertEqual(type(img_result), str)
        self.assertEqual(len(img_result), 5764)

    def test_get_height_pixels_one(self):
        result_heights = get_height_pixels(self.sample_results[:1])
        self.assertEqual(result_heights, {11: [321.1266479492]})

    def test_get_height_pixels_multiple(self):
        result_heights = get_height_pixels(self.sample_results)
        self.assertEqual(
            result_heights, {11: [321.1266479492, 334.520324707, 259.4705200195]}
        )

    def test_get_distance_meters(self):
        path_prefix = str(home_dir / "street2sat_utils/crop_info/")
        result_distance = get_distance_meters(
            self.sample_results,
            focal_length=3,
            pixel_height=2028,
            path_prefix=path_prefix,
        )
        self.assertEqual(result_distance, {"sugarcane": "17.753 meters"})

    def test_point_meters_away(self):
        coord = (0.6807162, 34.7490831)
        heading = 90
        meters_dict = {"sugarcane": "17.753 meters"}
        result_points = point_meters_away(coord, heading, meters_dict)
        self.assertEqual(
            result_points, {"sugarcane": (0.6807161999973629, 34.74924259009357)}
        )

    def test_get_new_points(self):
        time_dict = {
            datetime(2020, 12, 16, 8, 42, 54): 0,
            datetime(2020, 12, 16, 8, 45, 35): 1,
            datetime(2020, 12, 16, 8, 45, 41): 2,
        }

        coord_dict = {
            0: (0.6752619999999999, 34.7491525),
            1: (0.6805182999999999, 34.7490718),
            2: (0.6807162, 34.7490831),
        }

        distance_dict = {
            0: {"sugarcane": "20.397 meters"},
            1: {"sugarcane": "14.173 meters"},
            2: {"sugarcane": "15.826 meters"},
        }

        bearings, new_points = get_new_points(time_dict, coord_dict, distance_dict)

        expected_bearnings = {
            0: 269.12046874982326,
            1: 269.12046779505033,
            2: 269.2710504885695,
        }
        expected_new_points = {
            0: {"sugarcane": (0.675259187388663, 34.74896927843237)},
            1: {"sugarcane": (0.6805163456356776, 34.74894448705709)},
            2: {"sugarcane": (0.6807143913019371, 34.7489409332708)},
        }

        self.assertEqual(bearings, expected_bearnings)
        self.assertEqual(new_points, expected_new_points)
