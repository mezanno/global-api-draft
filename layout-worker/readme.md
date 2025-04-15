## Build instructions

1. Clone image processing server's sources
```sh
git clone --depth 1 https://github.com/soduco/directory-annotator-back.git code
```

2. Build the backend image using the main `docker-compose.yml` file.


## Debugging

Should you debug the individual image processing Docker image, you can build and test it this way:

```sh
# This assumes the current working directory is "worker/"

# Build the image
docker build -t soduco-imgproc --target soduco-imgproc .

# Run the image
docker run --rm -it --name imgproc --publish 8000:8000 soduco-imgproc

# Test (in another shell): health check
curl -X GET http://localhost:8000/health_check

# Test (in another shell): image processing
# -> replace "IMAGE_FILE.jpeg" by the actual path to your test image.
curl -X POST --data-binary @IMAGE_FILE.jpeg http://localhost:8000/imgproc/layout

```

