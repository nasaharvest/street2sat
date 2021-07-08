# syntax = docker/dockerfile:experimental
FROM pytorch/torchserve:0.3.0-cpu as base

USER root

FROM base as reqs
RUN apt-get update -y
RUN apt install libgl1-mesa-glx -y
RUN apt-get install 'ffmpeg' 'libsm6' 'libxext6'  -y
COPY gcp/inference/requirements.txt requirements.txt
RUN pip3 install --upgrade pip
RUN pip install -r requirements.txt

FROM reqs as build-torchserve
COPY gcp/inference/handler.py /home/model-server
COPY street2sat_utils/model_weights/*.pt /home/model-server

WORKDIR /home/model-server

ARG MODELS
RUN torch-model-archiver \
    --model-name street2sat \
    --version 1.0 \
    --serialized-file best.torchscript.pt \
    --handler handler.py \
    --export-path=model-store

CMD ["torchserve", "--start", "--ncs", "--model-store", "model-store", \
       "--models", "street2sat=street2sat.mar"]


