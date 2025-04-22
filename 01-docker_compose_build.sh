#!/bin/bash

# if the directory layout-worker/code does not exist, pull the code from the git repository
if [ ! -d "layout-worker/code" ]; then
    echo "Directory code does not exist. Cloning the repository..."
    git clone --depth 1 https://github.com/soduco/directory-annotator-back.git layout-worker/code
else
    echo "Directory layout-worker/code exists. You may want to update it."
fi

docker compose -f docker-compose.yml --project-name testfull up --build --force-recreate
