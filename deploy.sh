export CROPNOP_TAG=us-central1-docker.pkg.dev/bsos-geog-harvest1/street2sat-cropnop/street2sat-cropnop
export CROPNOP_URL="https://street2sat-cropnop-grxg7bzh2a-uc.a.run.app/predictions/cropnop"
export SEGMENT_TAG=us-central1-docker.pkg.dev/bsos-geog-harvest1/street2sat-segment/street2sat-segment
export SEGMENT_URL="https://street2sat-segment-grxg7bzh2a-uc.a.run.app/predictions/segmentation"
export SATELLITE_TAG=us-central1-docker.pkg.dev/bsos-geog-harvest1/street2sat-satellite/street2sat-satellite
export SATELLITE_URL="https://street2sat-satellite-grxg7bzh2a-uc.a.run.app/predictions/satellite"

export BUCKET_UPLOADED=street2sat-uploaded
export BUCKET_CROPS=street2sat-crops
export BUCKET_SEGMENTATIONS=street2sat-segmentations
export BUCKET_SATELLITE_IMGS=street2sat-satellite-imgs
export BUCKET_SATELLITE_IMGS_W_ARROW=street2sat-satellite-imgs-with-arrow
export BUCKET_SATELLITE_IMGS_PREDS=street2sat-satellite-imgs-predictions

echo "Create Google Cloud Buckets if they don't exist"
for BUCKET in $BUCKET_UPLOADED $BUCKET_CROPS $BUCKET_SEGMENTATIONS $BUCKET_SATELLITE_IMGS $BUCKET_SATELLITE_IMGS_W_ARROW $BUCKET_SATELLITE_IMGS_PREDS
do
        if [ "$(gsutil ls -b gs://$BUCKET)" ]; then
                echo "gs://$BUCKET already exists"
        else
                gsutil mb -l us-central1 gs://$BUCKET
        fi
done

echo "Checking if Artifact Registry needs to be created for storing docker images"
if [ -z "$(gcloud artifacts repositories list --format='get(name)' --filter "street2sat-cropnop")" ]; then
        gcloud artifacts repositories create "street2sat-cropnop" \
        --location "us-central1" \
        --repository-format docker
fi

docker build . -f Dockerfile.cropnop -t $CROPNOP_TAG
docker push $CROPNOP_TAG
gcloud run deploy street2sat-cropnop --image ${CROPNOP_TAG}:latest \
        --memory=4Gi \
        --concurrency=20 \
        --platform=managed \
        --region=us-central1 \
        --allow-unauthenticated

if [ -z "$(gcloud artifacts repositories list --format='get(name)' --filter "street2sat-segment")" ]; then
        gcloud artifacts repositories create "street2sat-segment" \
        --location "us-central1" \
        --repository-format docker
fi
docker build . -f Dockerfile.segment -t $SEGMENT_TAG
docker push $SEGMENT_TAG
gcloud run deploy street2sat-segment --image ${SEGMENT_TAG}:latest \
        --memory=16Gi \
        --concurrency=1 \
        --platform=managed \
        --region=us-central1 \
        --allow-unauthenticated


if [ -z "$(gcloud artifacts repositories list --format='get(name)' --filter "street2sat-satellite")" ]; then
        gcloud artifacts repositories create "street2sat-satellite" \
        --location "us-central1" \
        --repository-format docker
fi
docker build . -f Dockerfile.satellite -t $SATELLITE_TAG
docker push $SATELLITE_TAG
gcloud run deploy street2sat-satellite --image ${SATELLITE_TAG}:latest \
        --cpu=2 \
        --memory=8Gi \
        --concurrency=1 \
        --platform=managed \
        --region=us-central1 \
        --allow-unauthenticated

gcloud functions deploy trigger-street2sat-cropnop \
    --source=gcp/trigger_inference \
    --trigger-bucket=$BUCKET_UPLOADED \
    --allow-unauthenticated \
    --runtime=python39 \
    --entry-point=hello_gcs \
    --set-env-vars INFERENCE_URL="$CROPNOP_URL" \
    --timeout=300s

gcloud functions deploy trigger-street2sat-segment \
    --source=gcp/trigger_inference \
    --trigger-bucket=$BUCKET_CROPS \
    --allow-unauthenticated \
    --runtime=python39 \
    --entry-point=hello_gcs \
    --set-env-vars INFERENCE_URL="$SEGMENT_URL" \
    --timeout=300s

gcloud functions deploy trigger-street2sat-satellite \
    --source=gcp/trigger_inference \
    --trigger-bucket=$BUCKET_SATELLITE_IMGS_W_ARROW \
    --allow-unauthenticated \
    --runtime=python39 \
    --entry-point=hello_gcs \
    --set-env-vars INFERENCE_URL="$SATELLITE_URL" \
    --timeout=300s
    
gcloud functions deploy delete-street2sat-prediction \
    --source=gcp/delete-street2sat-prediction \
    --trigger-event=google.storage.object.delete \
    --trigger-resource=$BUCKET_UPLOADED \
    --allow-unauthenticated \
    --runtime=python39 \
    --entry-point=hello_gcs \
    --timeout=300s
