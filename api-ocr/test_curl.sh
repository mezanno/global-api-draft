#!/bin/bash

# Get first script parameter, initialize to 10 if not set
NUM=${1:-10}

API_NAME=predict

seq -f '{ "data": [ "%g" ] }' $NUM  \
  | parallel "curl -X POST -Ss http://localhost:7860/call/${API_NAME} -H 'Content-Type: application/json' -d {} | jq -r .event_id"  \
  | time parallel --tag -j $NUM curl -X GET -Ss http://localhost:7860/call/${API_NAME}/{}
