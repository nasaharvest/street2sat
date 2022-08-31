import re
import sys

from google.cloud import storage


def main(bucket_path, download_path):
    client = storage.Client()
    bucket = client.get_bucket("street2sat-model-predictions")
    download_bucket = client.get_bucket("street2sat-uploaded")

    bucket_path = bucket_path.lstrip("street2sat-model-predictions/")

    blob_list = []
    for blob in bucket.list_blobs(prefix=bucket_path):
        blob_list.append(blob.name)

    for blob_path in blob_list:
        blob_path = blob_path.replace("result_", "")
        blob_path = blob_path.replace(".jpg", ".JPG")
        blob = download_bucket.blob(blob_path)
        blob.download_to_filename(download_path + blob_path.split("/")[-1])


"""
Finds and downloads files from street2sat-uploaded that are in a folder in the street2sat-model-predictions
Usage:
python download_matched_files.py <path to folder with images in google cloud> <local directory>
ex. python download_matched_files.py street2sat-model-predictions/KENYA/2021-07-05-T1 /Users/madhavapaliyam/Downloads/
"""
if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
