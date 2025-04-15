# Preliminary global API logic for Mezanno
Preliminary work on a unified deployment and management of APIfied services for Mezanno, in a scalable way:
- API gateway
- Image cache
- Distributed task queue
- Monitoring
- Workers and their eventual wrappers

## Build and Run

### For layout analysis worker
Clone worker's sources:
```sh
git clone --depth 1 https://github.com/soduco/directory-annotator-back.git layout-worker/code
```

### When everything is ready
Then build and run everything at once:
```sh
docker compose up
```

## Use

Sample URL
`http://127.0.0.1:8200/layout?image_url=https://openapi.bnf.fr/iiif/image/v3/ark:/12148/bd6t543045578/f10/full/max/0/default.webp`


## Clean-up
```sh
docker compose down; \
docker image rm \
    global-api-draft-api-gateway \
    global-api-draft-cache \
    global-api-draft-layout-worker-wrapper \
    global-api-draft-layout-worker
```


## Architecture and notes
For now, the **layout service** is exposed directly (it is fast enough) from the API Gateway. The layout worker could be scaled, but this required the distribution of the Docker image over machines (manual replication or use registry) to be compatible with Docker Swarm. The API Gateway rewrites requests to the layout service so it uses the image cache whenever possible.

The **OCR service** is different: it requires long tasks which are queued in a 2nd-stage API (Gradio), then distributed to workers (using Celery for now).

## TODO
