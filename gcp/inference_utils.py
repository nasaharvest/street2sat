import tempfile
import time
from pathlib import Path

temp_dir = tempfile.gettempdir()


def get_name_from_uri(uri: str) -> str:
    uri_as_path = Path(uri)
    return "-".join(uri_as_path.parts[2:-1]) + "-" + uri_as_path.stem


def download_file(storage_client, uri: str) -> str:
    """
    Downloads file from Google Cloud Bucket
    """
    uri_as_path = Path(uri)
    bucket_name = uri_as_path.parts[1]
    file_name = "/".join(uri_as_path.parts[2:])
    bucket = storage_client.bucket(bucket_name)
    retries = 3
    blob = bucket.blob(file_name)
    for i in range(retries + 1):
        if blob.exists():
            print(f"HANDLER: Verified {uri} exists.")
            break
        if i == retries:
            raise ValueError(f"HANDLER ERROR: {uri} does not exist.")
        msg = f"HANDLER: {uri} doesn't exist, sleeping for 5 seconds and retrying."
        print(msg)
        time.sleep(5)
    local_path = f"{temp_dir}/{uri_as_path.name}"
    blob.download_to_filename(local_path)
    if not Path(local_path).exists():
        msg = f"HANDLER: {uri} from storage was not downloaded"
        raise FileExistsError(msg)
    print(f"HANDLER: Verified file downloaded to {local_path}")
    return local_path
