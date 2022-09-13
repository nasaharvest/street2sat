import collections
from typing import List, Optional

import pandas as pd
import reverse_geocoder as rg
from google.cloud import firestore, storage
from tqdm import tqdm

pd.options.display.max_colwidth = 600
pd.options.display.max_columns = None
pd.options.display.max_rows = None


"""
This script updates the csv located inside 'street2sat-database-csv' bucket 
with the associated predictions and changes from the firestore. 

Currently it does not store predictions, only these attributes: 

'input_img': the associated image name in street2sat-uploaded
'latitude': longitude from the image metadata
'longitude': longitude from the image metadata
'being_labeled': if the current image is being labeled or not
'country': country the image was taken in, retrieved from the folder name 
'admin1': admin1 for the location (retrieved from reverge_geocoder library)
'admin2': admin2 for the location (retrieved from reverse_geocoder library)
'cc': Country code (retreived from reverse_geocoder library)
'location': Town location (retrieved from reverse_geocoder library)
'test_set': if the current image is part of the test set TODO
'time': time from the image metadata
'focal_length': focal length from the image metadata
'pixel_height': pixel height from image metadata


This csv should be sufficient for dataset changes when going through the 'active learning' 
cycle for improving the YOLO detection model. 


In the future, if predictions are stored here as predictions improve, we can track 
the performance of street2sat over time using the past predictions. The firebase would
only store the latest predictions. 

"""


def get_images_already_being_labeled():
    """Gets images already labeled"""
    images_already_being_labelled = []
    csv_names = [
        blob.name
        for blob in client.list_blobs("street2sat-gcloud-labeling", prefix="")
        if blob.name.endswith(".csv")
    ]

    for csv_name in tqdm(csv_names, desc="Get already labeled"):
        uris = pd.read_csv(
            f"gs://street2sat-gcloud-labeling/{csv_name}", header=None, sep="\n"
        )[0]
        images_already_being_labelled += uris.to_list()

    # Ensure there are no duplicates in images already being labelled
    dupes = [
        item
        for item, count in collections.Counter(images_already_being_labelled).items()
        if count > 1
    ]
    dupes.remove("0")  # An index of 0 was erroneously output in previous csv
    assert (
        len(dupes) == 0
    ), "Found duplicates in images being labeled. One of the labeling tasks needs to be removed."
    return set(images_already_being_labelled)


# Initialize connections to cloud storage
client = storage.Client()
db = firestore.Client()
coll = db.collection("street2sat")

# csv storage bucket
uploaded_bucket = client.get_bucket("street2sat-database-csv")

database_info = pd.read_csv("gs://street2sat-database-csv/database-info.csv")

test_set_info = pd.read_csv("gs://street2sat-database-csv/test-set.csv")

# used to see if image is in test set or not
test_set_imgs = set(test_set_info["input_img"])

# to upadate any images from not being labaled to being labeled
already_labeled = get_images_already_being_labeled()


lat = []
lon = []
name = []
being_labeled = []
country: List[Optional[str]] = []
location = []
test_set = []
time_d = []
focal_length = []
pixel_height = []
dup_checker = set()
i = 0

# query limit amount bc queries can't live for more than 30 seconds
limit_amount = 1000

test_num = 0
nones_indexes = []


docs = coll.order_by("input_img").limit(limit_amount).stream()
while True:
    p_i = i
    for image in docs:
        d_image = image.to_dict()
        if d_image["coord"][0] is None or d_image["coord"][1] is None:
            nones_indexes.append(i)
            # temporarily append a  0,0 so that reverge_geocoder works right, fix later
            location.append((0, 0))
        else:
            location.append(d_image["coord"])
            # location.append(tuple(d_image["coord"]))

        lat.append(d_image["coord"][0])
        lon.append(d_image["coord"][1])

        name.append(d_image["input_img"])
        if d_image["input_img"] not in dup_checker:
            dup_checker.add(d_image["input_img"])
        else:
            print(f"Duplicate detected: {d_image} {i}")

        time_d.append(d_image["time"])
        focal_length.append(d_image["focal_length"])
        pixel_height.append(d_image["pixel_height"])

        # weird extra folder case
        if d_image["input_img"].split("/")[3].startswith("2021"):
            country.append(None)
        else:
            country.append(d_image["input_img"].split("/")[3])

        if d_image["input_img"] in already_labeled:
            being_labeled.append(True)
        else:
            being_labeled.append(False)

        if d_image["input_img"] in test_set_imgs:
            test_num += 1
            test_set.append(True)
        else:
            test_set.append(False)

        i += 1

    # multiple queries, next one starts where the previous ended
    docs = (
        coll.order_by("input_img")
        .start_after({"input_img": name[-1]})
        .limit(limit_amount)
        .stream()
    )
    assert (
        len(lat)
        == len(lon)
        == len(name)
        == len(being_labeled)
        == len(country)
        == len(test_set)
        == len(time_d)
        == len(focal_length)
        == len(pixel_height)
    ), "lengths incorrect"
    # these don't print every 10000 bc some images dont have locations
    print(f"Querying street2sat uploaded: {i}, {len(name)}")
    print(f"Test set images detected: {test_num}")
    if p_i == i:
        break


results = rg.search(location)
assert len(results) == len(lat), "Results and length of other data are off"
df_location_data = pd.DataFrame(results)


df = pd.DataFrame()
df["input_img"] = name
df["latitude"] = lat
df["longitude"] = lon
df["being_labeled"] = being_labeled
df["country"] = country
df["admin1"] = df_location_data["admin1"]
df["admin2"] = df_location_data["admin2"]
df["cc"] = df_location_data["cc"]
df["location"] = df_location_data["name"]
df["test_set"] = test_set
df["time"] = time_d
df["focal_length"] = focal_length
df["pixel_height"] = pixel_height

# fix images with no location
df.loc[nones_indexes, "admin1"] = None
df.loc[nones_indexes, "admin2"] = None
df.loc[nones_indexes, "cc"] = None
df.loc[nones_indexes, "location"] = None

# upload to bucket
blob = uploaded_bucket.blob("database-info.csv")
blob.upload_from_string(df.to_csv(), "text/csv")

print("Uploaded to google cloud!")
