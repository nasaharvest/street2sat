# Hannah Kerner
# June 15, 2021
# Convert directory of images to shapefile

import os
import exifread
import pandas as pd
import geopandas as gpd


def _get_if_exist(data, key):
    if key in data:
        return data[key]
    return None


def _convert_to_degrees(value):
    """
    Helper function to convert the GPS coordinates stored in the EXIF to degrees in float format
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
    lat = None
    lon = None

    gps_latitude = _get_if_exist(exif_data, "GPS GPSLatitude")
    gps_latitude_ref = _get_if_exist(exif_data, "GPS GPSLatitudeRef")
    gps_longitude = _get_if_exist(exif_data, "GPS GPSLongitude")
    gps_longitude_ref = _get_if_exist(exif_data, "GPS GPSLongitudeRef")

    if gps_latitude and gps_latitude_ref and gps_longitude and gps_longitude_ref:
        lat = _convert_to_degrees(gps_latitude)
        if gps_latitude_ref.values[0] != "N":
            lat = 0 - lat

        lon = _convert_to_degrees(gps_longitude)
        if gps_longitude_ref.values[0] != "E":
            lon = 0 - lon

    return lat, lon


def main(imgdir, shppath):
    # Create an empty dictionary for the locations
    locations = {}
    # Walk through the image files
    for root, subdir, files in os.walk(imgdir):
        for file in files:
            if file.endswith(".JPG"):
                # Open the file
                f = open(os.path.join(root, file), "rb")
                # Get the exif metadata
                meta = exifread.process_file(f)
                # Add the location metadata to the dictionary
                locations[os.path.join(root, file)] = get_exif_location(meta)

    # Turn the dictionary into a pandas dataframe
    df = pd.DataFrame.from_dict(
        locations, orient="index", columns=["Latitude", "Longitude"]
    )
    # Drop invalid rows
    df = df.dropna()
    # Convert the pandas dataframe to a geopandas dataframe
    gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.Longitude, df.Latitude))
    # Set the image file index to be its own column
    gdf["Image"] = gdf.index
    # Embed the image
    gdf["Link"] = None
    for r, row in gdf.iterrows():
        gdf.loc[r, "Link"] = "<img src='%s' width='300px'>" % row["Image"]
    # Save it as a shapefile
    gdf.to_file(shppath)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        argument_default=argparse.SUPPRESS,
        description="Convert a directory of images to a shapefile",
    )

    parser.add_argument("--imgdir", help="path to directory containing images")
    parser.add_argument(
        "--shppath", help="path for resulting shapefile, including filename"
    )

    args = parser.parse_args()

    main(**vars(args))
