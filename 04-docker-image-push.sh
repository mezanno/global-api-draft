#!/bin/bash
# Export docker images for swarm deployment

SERVICES="api-gateway cache layout-worker-wrapper layout-worker api-ocr ocr-worker"
REGISTRY=localhost:5000

TAG=${1:-latest}

# Login to the registry
echo -n "admin" | docker login --username admin --password-stdin ${REGISTRY}
for service in $SERVICES ; do
    # Check if the image exists
    if ! docker image inspect ${REGISTRY}/mezanno-${service}:${TAG} > /dev/null 2>&1; then
        echo "Image ${REGISTRY}/mezanno-${service}:${TAG} does not exist. Skipping export."
        continue
    fi
    # Export the image
    echo "Exporting ${REGISTRY}/mezanno-${service}:${TAG}"
    docker push ${REGISTRY}/mezanno-${service}:${TAG}
    if [ $? -ne 0 ]; then
        echo "Failed to export mezanno-${service}:${TAG}"
        continue
    fi
done;
