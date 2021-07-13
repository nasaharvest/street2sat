import logging
import os
import time

import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def hello_gcs(event, context):
    """Triggered by a change to a Cloud Storage bucket.
    Args:
         event (dict): Event payload.
         context (google.cloud.functions.Context): Metadata for the event.
    """
    logger.info(event)
    bucket_name = event["bucket"]
    blob_name = event["name"]
    src_path = f"gs://{bucket_name}/{blob_name}"
    logger.info(src_path)

    host = os.environ.get("INFERENCE_HOST")
    url = f"{host}/predictions/street2sat"
    logger.info(url)
    data = {"uri": src_path}
    for _ in range(3):
        logger.info("Sending request")
        response = requests.post(url, data=data)
        logger.info("Received response")
        logger.info(response.status_code)
        if response.status_code == 200:
            logger.info(response.json())
            break
        logger.error(f"Failed response: {response.raw}")
        time.sleep(5)
