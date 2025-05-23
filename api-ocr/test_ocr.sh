#!/bin/bash

# Get first script parameter, initialize to 10 if not set
NUM=${1:-10}

API_NAME=transcribe
# SERVER_URL=http://localhost:7860
# SERVER_URL=http://localhost:8204
SERVER_URL=https://api.mezanno.xyz/ocr

(for ii in $(seq 1 $NUM); do
  echo '{"data":["https://cache.mezanno.xyz/openapi.bnf.fr/iiif/image/v3/ark:/12148/bd6t543045578/f100/full/max/0/default.webp","[]"]}'
done ) | \
    parallel "curl -X POST -Ss ${SERVER_URL}/gradio_api/call/${API_NAME} -H 'Content-Type: application/json' -d {} | jq -r .event_id" \
  | \time parallel --tag -j $NUM "curl -X GET -Ss ${SERVER_URL}/gradio_api/call/${API_NAME}/{} | grep '^event' && ( echo -n 'done ' || echo -n 'error ' ) && date '+%Y-%m-%d %H:%M:%S' " \
