from datetime import datetime

import exifread  # type: ignore


def _get_if_exist(data, key):
    if key in data:
        return data[key]
    return None


def _convert_to_degress(value):
    """
    Helper function to convert the GPS coordinates stored in the EXIF to degress in float format
    :param value:
    :type value: exifread.utils.Ratio
    :rtype: float
    """
    d = float(value.values[0].num) / float(value.values[0].den)
    m = float(value.values[1].num) / float(value.values[1].den)
    s = float(value.values[2].num) / float(value.values[2].den)

    return d + (m / 60.0) + (s / 3600.0)


def get_exif_location(exif_data):
    """
    Returns the latitude and longitude, if available, from the provided exif_data (obtained through get_exif_data above)
    """
    gps_latitude = exif_data["GPS GPSLatitude"]
    gps_latitude_ref = exif_data["GPS GPSLatitudeRef"]
    gps_longitude = exif_data["GPS GPSLongitude"]
    gps_longitude_ref = exif_data["GPS GPSLongitudeRef"]
    
    lat = _convert_to_degress(gps_latitude)
    if gps_latitude_ref.values[0] != "N":
        lat = 0 - lat

    lon = _convert_to_degress(gps_longitude)
    if gps_longitude_ref.values[0] != "E":
        lon = 0 - lon

    return lat, lon


def get_exif_datetime(exif_data):
    date_time = _get_if_exist(exif_data, "Image DateTime")
    dt = datetime.strptime(str(date_time), "%Y:%m:%d %H:%M:%S")
    return dt


def get_exif_focal_length(exif_data):
    n = _get_if_exist(exif_data, "EXIF FocalLength")
    return n.values[0].num


def get_exif_image_height_width(exif_data):
    w = _get_if_exist(exif_data, "EXIF ExifImageWidth")
    h = _get_if_exist(exif_data, "EXIF ExifImageLength")
    return h.values[0], w.values[0]
