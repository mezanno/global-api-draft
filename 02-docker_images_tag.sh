#!/bin/bash
# This script is used to tag Docker images for the Mezanno project.
# Images are built locally

TIMESTAMP=$(date +%Y%m%d-%H%M)
REGISTRY=localhost:5000

SERVICES="api-gateway cache layout-worker-wrapper layout-worker api-ocr ocr-worker"

for service in $SERVICES ; do
    docker image tag testfull-${service}:latest ${REGISTRY}/mezanno-${service}:v${TIMESTAMP}
done;

echo "Tagged images:"
docker images | grep mezanno | grep v${TIMESTAMP}

echo "You may need to export the TAG with the following command:"
echo "export TAG=v${TIMESTAMP}"