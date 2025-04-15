FROM python:3.9-slim-bullseye

RUN apt-get update && apt-get install -y libglib2.0-0 && apt-get clean

# PERO OCR deps
RUN pip install -q --no-cache-dir https://github.com/jchazalon/pero-ocr/archive/refs/heads/master.zip
#    opencv-python-headless  # needed by driver, already implied in PERO deps
# https://www.lrde.epita.fr/~jchazalo/SHARE/pero_eu_cz_print_newspapers_2020-10-09.tar.gz
# Size: 67MB

# FIXME deploy on volume after build
ADD ./pero_eu_cz_print_newspapers_2020-10-09.tar.gz /data/pero_ocr/
# Will all following files:
# /data/pero_ocr/pero_eu_cz_print_newspapers_2020-10-07:
# - ParseNet.pb
# - checkpoint_350000.pth
# - config.ini
# - ocr_engine.json
#
# We could also cache this:
# Downloading: "https://download.pytorch.org/models/vgg16-397923af.pth" to /root/.cache/torch/hub/checkpoints/vgg16-397923af.pth
# Size: 528MB

# FIXME deploy on volume after build
COPY vgg16-397923af.pth /root/.cache/torch/hub/checkpoints/vgg16-397923af.pth

COPY requirements.txt /app/
RUN pip install -r /app/requirements.txt
# ENV LC_ALL=C
COPY pero_ocr_driver.py worker.py celeryconfig.py /app/
WORKDIR /app

ENV PERO_CONFIG_DIR=/data/pero_ocr/pero_eu_cz_print_newspapers_2020-10-07/
ENV C_FORCE_ROOT=1
# Wrong CMD?
CMD celery -A worker worker --loglevel=info
