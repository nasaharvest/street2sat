from google.cloud import storage
import re
import sys




def main(bucket_path, download_path):
    client = storage.Client()
    bucket = client.get_bucket('street2sat-model-predictions')
    download_bucket = client.get_bucket('street2sat-uploaded')


    bucket_path = bucket_path.lstrip('street2sat-model-predictions/')

    blob_list = []
    for blob in bucket.list_blobs(prefix=bucket_path):
        blob_list.append(blob.name)

    for blob_path in blob_list:
        blob_path = blob_path.replace('result_', '')
        blob_path = blob_path.replace('.jpg', '.JPG')
        blob = download_bucket.blob(blob_path)
        blob.download_to_filename(download_path + blob_path.split('/')[-1])
        
if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
