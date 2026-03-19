FROM python:3.12-slim as build-env

# ----------------------------
# Build layout-worker (C++)
# ----------------------------
WORKDIR /tmp/app-build

RUN apt-get update && \
    apt-get install -y cmake unzip g++ perl-openssl-defaults libfindbin-libs-perl libtesseract-dev libssl-dev && \
    pip install conan

# Layout worker sources
COPY layout-worker/code/conanfile.py /tmp/app-build/

RUN touch CMakeLists.txt && \
    conan remote add lrde-public https://artifactory.lrde.epita.fr/artifactory/api/conan/lrde-public --index 0 && \
    conan profile detect && \
    conan install . -of build -s compiler.cppstd=20 --build=missing -o onetbb/*:tbbproxy=False

COPY layout-worker/code/CMakeLists.txt /tmp/app-build/
COPY layout-worker/code/sources /tmp/app-build/sources
COPY layout-worker/code/thirdparty /tmp/app-build/thirdparty

RUN cmake -S . -B build --preset conan-release && \
    cmake --build ./build && \
    cmake --install ./build --prefix /app


# ----------------------------
# Runtime: server + celery
# ----------------------------
FROM python:3.12-slim as runtime

RUN apt-get update && \
    apt-get install --no-install-recommends -q -y libtesseract5 tesseract-ocr-fra ca-certificates && \
    apt-get install --no-install-recommends -y libtbb12 libtbbbind-2-5 libtbbmalloc2 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

ENV LD_LIBRARY_PATH=/app/bin/lib

WORKDIR /app

COPY --from=build-env /app /app

# Celery task code (re-uses existing layout-celery-worker implementation)
COPY layout-celery-worker/requirements.txt /app/requirements.txt
COPY layout-celery-worker/celeryconfig.py /app/celeryconfig.py
COPY layout-celery-worker/worker.py /app/worker.py

# Ensure sidecar Celery task calls its co-located server.
ENV LAYOUT_SERVICE_URL=http://127.0.0.1:8000/imgproc/layout

RUN pip install --no-cache-dir -r /app/requirements.txt

EXPOSE 8000

CMD ["/bin/sh", "-c", "/app/bin/server --port 8000 & exec celery --app=worker.celery worker -Q layout --concurrency=1 --loglevel=INFO"]

