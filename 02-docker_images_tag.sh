#!/bin/bash
# This script is used to tag Docker images for the Mezanno project.
# Images are built locally

TIMESTAMP=$(date +%Y%m%d-%H%M)

SERVICES="api-gateway cache layout-worker-wrapper layout-worker api-ocr ocr-worker"

for service in $SERVICES ; do
    docker image tag testfull-${service}:latest mezanno-${service}:v${TIMESTAMP}
done;
