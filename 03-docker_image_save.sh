#!/bin/bash
# Export docker images for swarm deployment

SERVICES="api-gateway cache layout-worker-wrapper layout-worker api-ocr ocr-worker"
DESTINATION=~/tmp/mezanno-images

TAG=${1:-latest}

# Use pigz for faster compression if available, otherwise fall back to gzip
PIGZ=$(command -v pigz)
if [ -z "$PIGZ" ]; then
    echo "pigz not found, using gzip instead."
    PIGZ=gzip
fi

# Create destination directory if it doesn't exist
mkdir -p ${DESTINATION}

for service in $SERVICES ; do
    # Check if the image exists
    if ! docker image inspect mezanno-${service}:${TAG} > /dev/null 2>&1; then
        echo "Image mezanno-${service}:${TAG} does not exist. Skipping export."
        continue
    fi
    # Check if the destination image already exists
    if [ -f ${DESTINATION}/mezanno-${service}-${TAG}.tar.gz ]; then
        echo "File ${DESTINATION}/mezanno-${service}-${TAG}.tar.gz already exists. Skipping export."
        continue
    fi
    # Export the image
    echo "Exporting mezanno-${service}:${TAG} to ${DESTINATION}/mezanno-${service}-${TAG}.tar.gz"
    docker save mezanno-${service}:${TAG} | $PIGZ > ${DESTINATION}/mezanno-${service}-${TAG}.tar.gz
done;
