import os

# from pero_ocr_driver import PERO_driver

from celery import Celery
import cv2
import requests
import numpy as np

# Celery configuration
CELERY_BROKER_URL = os.environ["CELERY_BROKER_URL"]  # 'amqp://rabbitmq:rabbitmq@rabbit:5672/'
CELERY_RESULT_BACKEND = os.environ["CELERY_RESULT_BACKEND"]  # 'rpc://'


# PERO configuration
PERO_CONFIG_DIR = os.environ["PERO_CONFIG_DIR"]

# Initialize Celery
celery = Celery("worker", broker=CELERY_BROKER_URL, backend=CELERY_RESULT_BACKEND) # 'ocr_worker', 
celery.config_from_object('celeryconfig')

# Define our OCR task
@celery.task()
def run_ocr(image_url, image_regions):

    ## FIXME take image url and regions as input
    ## Parse and validate with Pydantic

    # use requests to download the image synchronously
    r = requests.get(image_url, timeout=10.0)
    if r.status_code != 200:
        return {"error": "Cannot download image."}
    image_data = r.content

    # Check if the image data is None
    # or if the content type is not image/jpg
    if r.headers.get('Content-Type') != 'image/jpeg':
        return {"error": "Request does not contain a valid image."}
    if image_data is None:
        return {"error": "Request contains no image data."}
    
    # Read the image data into a numpy array using OpenCV
    # Beware of channels order
    image_numpy = cv2.imdecode(np.frombuffer(image_data, np.uint8), cv2.IMREAD_COLOR)
    if image_numpy is None:
        return {"error": "Cannot open image."}
    # Convert the image to RGB format
    image_numpy = cv2.cvtColor(image_numpy, cv2.COLOR_BGR2RGB)


    # We expect image/jpg Content type
    if image_data is None:
        return {"error": "Request contains no image data."}

    # Fake response to test
    return {
        "image_url": image_url,
        "image_regions": image_regions,
        "image_shape": image_numpy.shape,
    }


    # ocr_engine = PERO_driver(PERO_CONFIG_DIR)
    # # TODO loop over image regions
    # ocr_results = ocr_engine.detect_and_recognize(image_numpy)
    # ocr_results = "\n".join([textline.transcription for textline in ocr_results])
    # return {"content": ocr_results}
