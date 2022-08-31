import json
from pydoc import cli

from google.cloud import firestore, storage
from tqdm import tqdm

"""
This script will create a new bucket on google cloud. 

The input folder/bucket will be used to pull the same named images
from the street2sat uploaded bucket and copy into the new bucket. 
"""

INPUT_BUCKET = "street2sat-model-predictions"
INPUT_FOLDER = ""

OUTPUT_BUCKET_NAME = "street2sat-iiasa"


client = storage.Client()

all_paths = [
    blob.name for blob in tqdm(client.list_blobs(INPUT_BUCKET, prefix=INPUT_FOLDER))
]

print(f"{len(all_paths)} images were found. Copying to {OUTPUT_BUCKET_NAME}.")

input_bucket = client.get_bucket(INPUT_BUCKET)
street2sat_uploaded_bucket = client.get_bucket("street2sat-uploaded")
try:
    new_bucket = client.create_bucket(OUTPUT_BUCKET_NAME, location="us-east1")
except:
    print("BUCKET ALREADY EXISTS!")
    new_bucket = client.get_bucket(OUTPUT_BUCKET_NAME)


failed = []
for path in tqdm(all_paths):
    # convert from result_ format for model-predictions bucket to normal name for street2sat-uploaded bucket
    new_path = path.replace("result_", "", 1)
    new_path = new_path.replace(".jpg", ".JPG", 1)
    old_blob = street2sat_uploaded_bucket.blob(new_path)
    # copy from street2sat uploaded into new_bucket
    try:
        new_blob = street2sat_uploaded_bucket.copy_blob(old_blob, new_bucket)
    except:
        failed.append(new_path)
        print("FAILED", path, new_path)


print(failed)


"""
['USA/2021-08-20-croptour/G0013252.JPG', 'USA/2021-08-20-croptour/G0013296.JPG', 'USA/2021-08-20-croptour/G0013364.JPG', 
'USA/2021-08-20-croptour/G0013675.JPG', 'USA/2021-08-20-croptour/G0013775.JPG', 'USA/2021-08-20-croptour/G0013898.JPG', 
'USA/2021-08-20-croptour/G0014008.JPG', 'USA/2021-08-20-croptour/G0014017.JPG', 'USA/2021-08-20-croptour/G0014130.JPG', 
'USA/2021-08-20-croptour/G0014196.JPG', 'USA/2021-08-20-croptour/G0014305.JPG', 'USA/2021-08-20-croptour/G0014370.JPG', 
'USA/2021-08-20-croptour/G0014515.JPG', 'USA/2021-08-20-croptour/G0014551.JPG', 'USA/2021-08-20-croptour/G0014619.JPG', 
'USA/2021-08-20-croptour/G0014622.JPG', 'USA/2021-08-20-croptour/G0014777.JPG', 'USA/2021-08-20-croptour/G0015017.JPG', 
'USA/2021-08-20-croptour/G0015244.JPG', 'USA/2021-08-20-croptour/G0015326.JPG', 'USA/2021-08-20-croptour/G0015329.JPG', 
'USA/2021-08-20-croptour/G0015393.JPG', 'USA/2021-08-20-croptour/G0015394.JPG', 'USA/2021-08-20-croptour/G0015489.JPG', 
'USA/2021-08-20-croptour/G0015623.JPG', 'USA/2021-08-20-croptour/G0015646.JPG', 'USA/2021-08-20-croptour/G0015963.JPG', 
'USA/2021-08-20-croptour/G0016075.JPG', 'USA/2021-08-20-croptour/G0016143.JPG', 'USA/2021-08-20-croptour/G0016162.JPG', 
'USA/2021-08-20-croptour/G0016165.JPG', 'USA/2021-08-20-croptour/G0016254.JPG', 'USA/2021-08-20-croptour/G0016686.JPG', 
'USA/2021-08-20-croptour/G0016790.JPG', 'USA/2021-08-20-croptour/G0016879.JPG', 'USA/2021-08-20-croptour/G0016880.JPG', 
'USA/2021-08-20-croptour/G0016886.JPG', 'USA/2021-08-20-croptour/G0017087.JPG', 'USA/2021-08-20-croptour/G0017166.JPG', 
'USA/2021-08-20-croptour/G0017303.JPG', 'USA/2021-08-20-croptour/G0017359.JPG', 'USA/2021-08-20-croptour/G0017412.JPG', 
'USA/2021-08-20-croptour/G0017421.JPG', 'USA/2021-08-20-croptour/G0017474.JPG', 'USA/2021-08-20-croptour/G0017505.JPG', 
'USA/2021-08-20-croptour/G0017627.JPG', 'USA/2021-08-20-croptour/G0017691.JPG', 'USA/2021-08-20-croptour/G0017968.JPG', 
'USA/2021-08-20-croptour/G0028037.JPG', 'USA/2021-08-20-croptour/G0028404.JPG', 'USA/2021-08-20-croptour/G0028524.JPG', 
'USA/2021-08-20-croptour/G0028544.JPG', 'USA/2021-08-20-croptour/G0028566.JPG', 'USA/2021-08-20-croptour/G0028592.JPG', 
'USA/2021-08-20-croptour/G0028606.JPG', 'USA/2021-08-20-croptour/G0028904.JPG', 'USA/2021-08-20-croptour/G0029004.JPG', 
'USA/2021-08-20-croptour/G0029046.JPG', 'USA/2021-08-20-croptour/G0029057.JPG', 'USA/2021-08-20-croptour/G0029096.JPG', 
'USA/2021-08-20-croptour/G0029108.JPG', 'USA/2021-08-20-croptour/G0029144.JPG', 'USA/2021-08-20-croptour/G0029244.JPG', 
'USA/2021-08-20-croptour/G0029271.JPG', 'USA/2021-08-20-croptour/G0029332.JPG', 'USA/2021-08-20-croptour/G0029520.JPG', 
'USA/2021-08-20-croptour/G0029675.JPG', 'USA/2021-08-20-croptour/G0029749.JPG', 'USA/2021-08-20-croptour/G0029776.JPG', 
'USA/2021-08-20-croptour/G0030023.JPG', 'USA/2021-08-20-croptour/G0030045.JPG', 'USA/2021-08-20-croptour/G0030111.JPG', 
'USA/2021-08-20-croptour/G0030145.JPG', 'USA/2021-08-20-croptour/G0030147.JPG', 'USA/2021-08-20-croptour/G0030370.JPG', 
'USA/2021-08-20-croptour/G0030395.JPG', 'USA/2021-08-20-croptour/G0050755.JPG', 'USA/2021-08-20-croptour/G0050943.JPG', 
'USA/2021-08-20-croptour/G0051075.JPG', 'USA/2021-08-20-croptour/G0051118.JPG', 'USA/2021-08-20-croptour/G0051123.JPG', 
'USA/2021-08-20-croptour/G0051226.JPG', 'USA/2021-08-20-croptour/G0051229.JPG', 'USA/2021-08-20-croptour/G0051251.JPG', 
'USA/2021-08-20-croptour/G0051418.JPG', 'USA/2021-08-20-croptour/G0051517.JPG', 'USA/2021-08-20-croptour/G0051534.JPG', 
'USA/2021-08-20-croptour/G0051724.JPG', 'USA/2021-08-20-croptour/G0051794.JPG', 'USA/2021-08-20-croptour/G0051851.JPG', 
'USA/2021-08-20-croptour/G0051857.JPG', 'USA/2021-08-20-croptour/G0052077.JPG', 'USA/2021-08-20-croptour/G0052160.JPG', 
'USA/2021-08-20-croptour/G0052175.JPG', 'USA/2021-08-20-croptour/G0052187.JPG', 'USA/2021-08-20-croptour/G0052194.JPG', 
'USA/2021-08-20-croptour/G0052208.JPG', 'USA/2021-08-20-croptour/G0052303.JPG', 'USA/2021-08-20-croptour/G0052353.JPG', 
'USA/2021-08-20-croptour/G0052419.JPG', 'USA/2021-08-20-croptour/G0052471.JPG', 'USA/2021-08-20-croptour/G0052539.JPG', 
'USA/2021-08-20-croptour/G0052546.JPG', 'USA/2021-08-20-croptour/G0052559.JPG', 'USA/2021-08-20-croptour/G0052585.JPG', 
'USA/2021-08-20-croptour/G0052658.JPG', 'USA/2021-08-20-croptour/G0052687.JPG', 'USA/2021-08-20-croptour/G0063016.JPG', 
'USA/2021-08-20-croptour/G0063028.JPG']
"""
