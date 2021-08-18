from datetime import datetime
from pathlib import Path
from unittest import TestCase

from street2sat_utils.client import Prediction, calculate_crop_coords

home_dir = Path(__file__).parent.parent.parent

image_path = home_dir / "example_images/GP__1312.JPG"


class TestClient(TestCase):

    sample_results = [
        {
            "class": 11,
            "confidence": 0.6548390984535217,
            "name": "sugarcane",
            "xmax": 646.2578735351562,
            "xmin": 474.721435546875,
            "ymax": 1155.9974365234375,
            "ymin": 834.8707885742188,
        },
        {
            "class": 11,
            "confidence": 0.6288385987281799,
            "name": "sugarcane",
            "xmax": 1398.083251953125,
            "xmin": 1242.162109375,
            "ymax": 1085.2777099609375,
            "ymin": 750.7573852539062,
        },
        {
            "class": 11,
            "confidence": 0.6045596599578857,
            "name": "sugarcane",
            "xmax": 2100.96728515625,
            "xmin": 1986.495849609375,
            "ymax": 1043.10986328125,
            "ymin": 783.6393432617188,
        },
    ]

    def test_prediction_from_img_path(self):
        pred = Prediction.from_img_path(img_path=str(image_path))
        self.assertEqual(pred.coord, (0.6752619999999999, 34.7491525))
        self.assertEqual(pred.distances, {"sugarcane": 20.397414224803118})
        self.assertEqual(pred.focal_length, 3)
        self.assertEqual(pred.img.shape, (2028, 2704, 3))
        self.assertEqual(pred.pixel_height, 2028)
        self.assertEqual(len(pred.results), 32)
        self.assertEqual(pred.results[:3], self.sample_results)
        self.assertEqual(pred.time, datetime(2020, 12, 16, 8, 42, 54))

    def test_prediction_from_img_bytes(self):
        img_bytes = open(image_path, "rb")
        pred = Prediction.from_img_bytes(img_bytes=img_bytes, name=str(image_path))
        self.assertEqual(pred.coord, (0.6752619999999999, 34.7491525))
        self.assertEqual(pred.distances, {"sugarcane": 20.397414224803118})
        self.assertEqual(pred.focal_length, 3)
        self.assertEqual(pred.img.shape, (2028, 2704, 3))
        self.assertEqual(pred.pixel_height, 2028)
        self.assertEqual(len(pred.results), 32)
        self.assertEqual(pred.results[:3], self.sample_results)
        self.assertEqual(pred.time, datetime(2020, 12, 16, 8, 42, 54))

    def test_prediction_from_results_and_tags(self):
        tags = {
            "time": datetime(2020, 12, 16, 8, 42, 54),
            "focal_length": 3,
            "coord": (0, 0),
            "pixel_height": 0,
        }
        pred = Prediction.from_results_and_tags(
            results=self.sample_results, tags=tags, name=str(image_path)
        )
        self.assertEqual(pred.coord, (0, 0))
        self.assertEqual(pred.distances, {"sugarcane": 0.0})
        self.assertEqual(pred.focal_length, 3)
        self.assertEqual(pred.pixel_height, 0)
        self.assertEqual(len(pred.results), 3)
        self.assertEqual(pred.results, self.sample_results)
        self.assertEqual(pred.time, datetime(2020, 12, 16, 8, 42, 54))

    def test_get_new_points(self):
        paths = [home_dir / f"example_images/GP__131{i}.JPG" for i in ["2", "3", "4"]]
        preds = [Prediction.from_img_path(p) for p in paths]
        preds = calculate_crop_coords(preds)
        crop_coords = [p.crop_coord for p in preds]

        expected_crop_coords = [
            {"sugarcane": (0.6752591873315441, 34.748969274711484)},
            {"sugarcane": (0.6805255576596102, 34.748944676649)},
            {"sugarcane": (0.6807243040599843, 34.74894115130783)},
        ]

        for actual, expected in zip(crop_coords, expected_crop_coords):
            self.assertEqual(expected, actual)
