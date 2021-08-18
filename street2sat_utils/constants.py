from pathlib import Path

HOME_DIR = Path(__file__).parent.parent
MODEL_PATH = HOME_DIR / "model_weights/best.pt"

GOPRO_SENSOR_HEIGHT = 4.55

CROP_TO_HEIGHT_DICT = {
    "tobacco": 0,
    "coffee": 0,
    "banana": 0,
    "tea": 0,
    "beans": 0,
    "maize": 3000,
    "sorghum": 0,
    "millet": 0,
    "sweet_potatoes": 0,
    "cassava": 0,
    "rice": 0,
    "sugarcane": 4000,
}

CROP_CLASSES = list(CROP_TO_HEIGHT_DICT.keys())
