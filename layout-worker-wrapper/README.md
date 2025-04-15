# Mock server for workers

Exposes correct API and returns a constant payload.
Will eventually really use the cache to check internal connectivity.

## Usage
This service should be built using the main dockercompose file.

## Manually build and test the image

Generate or update the `requirements.txt` file for Docker image preparation with `uv` using:
```bash
# Assume current working directory is `worker`
uv export -o requirements.txt
```

Manual build for inspection using:
```bash
docker build -t mock-worker .
```

Manually run:
```bash
docker run --rm -it -p 8000:8000 mock-worker
```

Test:
```bash
curl -X GET http://localhost:8000/layout
# Should return `{"message": "ok"}` for now, later with a better reply
```
