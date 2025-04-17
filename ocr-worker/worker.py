import os
import json


from celery import Celery
import cv2
import requests
import numpy as np

from pero_ocr_driver import PERO_driver

# FIXME use pydantic and make sure we have type declarations compatible with Python 3.9
# class ImageRegion(BaseModel):
#     xtl: float|int
#     ytl: float|int
#     xbr: float|int
#     ybr: float|int
# ImageRegionList: TypeAlias = list[ImageRegion]
# ImageRegionListModel = TypeAdapter(ImageRegionList)

# class LineTranscription(BaseModel):
#     text: str
#     confidence: float
#     polygon: list[list[float]]
#     line_id: int

# class OCREngineInfo(BaseModel):
#     name: str
#     code_version: str
#     model_version: str

# class OCRResult(BaseModel):
#     ocr_engine: OCREngineInfo
#     lines: list[LineTranscription]

# Celery configuration
CELERY_BROKER_URL = os.environ["CELERY_BROKER_URL"]  # 'amqp://rabbitmq:rabbitmq@rabbit:5672/'
CELERY_RESULT_BACKEND = os.environ["CELERY_RESULT_BACKEND"]  # 'rpc://'

VALID_IMAGE_TYPES = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp']

# PERO configuration
PERO_CONFIG_DIR = os.environ["PERO_CONFIG_DIR"]
PERO_MODEL_VERSION = os.path.basename(PERO_CONFIG_DIR)
PERO_CODE_VERSION = "https://github.com/DCGM/pero-ocr?rev=57c07b1d192859bc4ec71859769d4f624c50dbfc"

# Initialize Celery
celery = Celery("worker", broker=CELERY_BROKER_URL, backend=CELERY_RESULT_BACKEND) # 'ocr_worker', 
celery.config_from_object('celeryconfig')

# Define our OCR task
@celery.task()
def run_ocr(image_url: str, image_regions: dict) -> dict:
    print(f"Processing image: {image_url}")

    bboxes_xyxy = []
    for region in image_regions:
        # Convert the region to a tuple of integers
        bbox = tuple(map(lambda x: max(0, int(x)), [region[key] for key in ["xtl", "ytl", "xbr", "ybr"]]))
        bboxes_xyxy.append(bbox)
    # bboxes_xyxy = [(0, 0, 100, 100), (200, 200, 300, 300)]



    # use requests to download the image synchronously
    r = requests.get(image_url, timeout=10.0)
    if r.status_code != 200:
        return {"error": "Cannot download image."}
    image_data = r.content

    # Check if the image data is None
    # or if the content type is not image/jpg
    if r.headers.get('Content-Type') not in VALID_IMAGE_TYPES:
        return {"error": "Request does not contain a valid image. Valid types are: " + ", ".join(VALID_IMAGE_TYPES)}
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
    # return {
    #     "image_url": image_url,
    #     "image_regions": image_regions,
    #     "image_shape": image_numpy.shape,
    # }

    # if the bboxes are empty, generate one with the full image
    if len(bboxes_xyxy) == 0:
        bboxes_xyxy = [(0, 0, image_numpy.shape[1], image_numpy.shape[0])]


    # Run the OCR engine
    print("Calling OCR engine...")
    ocr_engine = PERO_driver(PERO_CONFIG_DIR)
    ocr_results = ocr_engine.detect_and_recognize(image_numpy, bboxes_xyxy)
    # ocr_results = "\n".join([textline.transcription for textline in ocr_results])
    return {
        "ocr_engine": {
            "name": "PERO OCR",
            "code_version": PERO_CODE_VERSION,
            "model_version": PERO_MODEL_VERSION,
        },
        "transcriptions": [
            {
                "region": region,
                "lines": lines
            } for region, lines in zip(bboxes_xyxy, ocr_results)
        ]
    }
