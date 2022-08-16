export TAG=us-central1-docker.pkg.dev/bsos-geog-harvest1/street2sat/street2sat
export BUCKET=street2sat-uploaded
export URL="https://street2sat-grxg7bzh2a-uc.a.run.app"

docker build . -t $TAG
docker push $TAG
gcloud run deploy street2sat --image ${TAG}:latest \
        --memory=4Gi \
        --platform=managed \
        --region=us-central1 \
        --allow-unauthenticated

gcloud functions deploy trigger-street2sat \
    --source=gcp/trigger_inference \
    --trigger-bucket=$BUCKET \
    --allow-unauthenticated \
    --runtime=python39 \
    --entry-point=hello_gcs \
    --set-env-vars INFERENCE_HOST="$URL" \
    --timeout=300s
    
gcloud functions deploy delete-street2sat-prediction \
    --source=gcp/delete-street2sat-prediction \
    --trigger-event=google.storage.object.delete \
    --trigger-resource=$BUCKET \
    --allow-unauthenticated \
    --runtime=python39 \
    --entry-point=hello_gcs \
    --timeout=300s    
