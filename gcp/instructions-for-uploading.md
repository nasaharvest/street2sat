# Instructions for uploading images

## Getting Access (only done once)
1. Request access to upload images from NASA Harvest.
2. Receive email with subject: **Google Cloud role upade for "street2sat-uploaded"**

    <img src="assets/street2sat-email.png"/>

3. Navigate to the link provided, select your country, check the box and click **Agree and Continue**:

    <img src="assets/street2sat-gcloud.png" width=80%/>

## Uploading images
The following format `<COUNTRY>/<YYYY>-<MM>-<DD>-<folder-name>/*.jpg` will be used for keeping the bucket organized.
1. Create a folder for the country where the images were taken (if it does not already exist).
    <img src="assets/street2sat-upload-country.png" width=80%/>

2. Navigate to the `<COUNTRY>` and select **Upload folder**.

    <img src="assets/street2sat-upload.png" width=80%/>

3. Selecting the folder with images:
    - Ensure the folder name contains the date at the beginning in the format YYYY-MM-DD
    - Ensure the folder name does not contain spaces
    <img src="assets/street2sat-upload-images.png" width=80%/>

4. Verifying that the images were uploaded

    <img src="assets/street2sat-upload-done.png" width=80%/>


That's it! 

Next time new images are available you can navigate directly to https://console.cloud.google.com/storage/browser/street2sat-uploaded and follow the steps in **Uploading images**


