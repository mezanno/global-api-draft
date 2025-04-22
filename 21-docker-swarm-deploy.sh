#!/bin/bash

REGISTRY="http://localhost:5000"
export REGISTRY


usage() {
    echo "Usage: $0 [-d] <tag>"
    echo "Deploys the Docker stack to the swarm cluster."
    echo "Arguments:"
    echo "  -d      Enable debug mode."
    echo "  <tag>   The tag of the Docker images to deploy."
}

# Parse command line arguments
while getopts ":d" opt; do
    case $opt in
        d)
            DEBUG=1
            ;;
        \?)
            echo "Invalid option: -$OPTARG" >&2
            usage
            exit 1
            ;;
        :)
            echo "Option -$OPTARG requires an argument." >&2
            usage
            exit 1
            ;;
    esac
done
shift $((OPTIND -1))
# Check if a tag is provided
if [ -z "$1" ]; then
    echo "Error: No tag provided."
    usage
    exit 1
fi
# Set the tag variable
TAG=$1
export TAG

# Login to the local registry
echo -n "admin" | docker login --username admin --password-stdin ${REGISTRY}

# if debug
if [ "$DEBUG" ]; then
    # Display the substitued values in the config file for debugging
    docker stack config -c docker-compose-swarm.yml
else
    echo "Deploying the stack..."
    # Real command to deploy the stack
    docker stack deploy -c docker-compose-swarm.yml --with-registry-auth --resolve-image always --prune mezanno-api
fi
