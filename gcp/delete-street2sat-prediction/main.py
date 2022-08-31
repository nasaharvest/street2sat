# The given script creates a CLoud Function to that is triggered when an image file is deleted from the street2sat-uploaded bucket
# and then proceeds to delete the corresponding record from the Firestore DB.
import logging

from google.cloud import firestore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
db = firestore.Client()


def hello_gcs(event, context):
    """Triggered by a change to a Cloud Storage bucket.
    Args:
         event (dict): Event payload.
         context (google.cloud.functions.Context): Metadata for the event.
    """
    # Getting the image name
    img_path = event["name"]

    # Extracting the document name from the file path
    doc_ref = img_path.replace("/", "-").split(".")[0]
    logging.info("The name of the document is " + doc_ref + ".")

    # Getting the document reference
    doc = db.collection("street2sat").document(doc_ref)
    doc_check = doc.get()

    # Checking if the document reference exists in the collections and deleting it.
    if doc_check.exists:
        logger.info(
            "The record associated with the image file exists in the Firestore DB."
        )
        logger.info("Deleting the given document.")
        doc.delete()
        logger.info("Document has been deleted.")
    else:
        logger.info(
            "No such record associated with the image file exists in the Firestore DB!."
        )
