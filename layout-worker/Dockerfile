FROM python:3.10-slim-bookworm as build-env

# Update package lists and install any necessary packages
RUN apt-get update && \
    apt-get install -y cmake unzip g++ perl-openssl-defaults libfindbin-libs-perl libtesseract-dev libssl-dev

# Install conan with pip
RUN pip install conan

# Set the working directory
WORKDIR /tmp/app-build

# Install the conan dependencies
COPY code/conanfile.py /tmp/app-build/
RUN touch CMakeLists.txt && \
    conan remote add lrde-public https://artifactory.lrde.epita.fr/artifactory/api/conan/lrde-public --index 0 && \
    conan profile detect && \
    conan install . -of build -s compiler.cppstd=20 --build=missing -o onetbb/*:tbbproxy=False

# Copy the source code and install deps
COPY code/CMakeLists.txt /tmp/app-build/
COPY code/sources /tmp/app-build/sources
COPY code/thirdparty /tmp/app-build/thirdparty

# Build the application
RUN cmake -S . -B build --preset conan-release && \
    cmake --build ./build && \
    cmake --install ./build --prefix /app 


#######################################################################
### Second stage: runtime environment for CLI and improg/bakcend   ####
#######################################################################
FROM debian:bookworm-slim as directory-annotator-imgproc

RUN apt-get update && \
    apt-get install --no-install-recommends -q -y libtesseract5 tesseract-ocr-fra ca-certificates

# Copy the built application from the build environment
COPY --from=build-env /app /app

RUN apt-get update && \
    apt-get install --no-install-recommends -y libtbb12 libtbbbind-2-5 libtbbmalloc2 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Expose any necessary ports
EXPOSE 8000

# set environment variables
ENV LD_LIBRARY_PATH=/app/bin/lib

# Set the working directory
WORKDIR /app/bin

# Define the command to run the application
CMD /app/bin/server --port 8000
# CMD /app/bin/server --prefix "${SCRIPT_NAME}" --port 8000 --storage-uri "${SODUCO_STORAGE_URI}"

