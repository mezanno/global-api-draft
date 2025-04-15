"""
Interface to transcribe images, forwarding requests to a task queue.
"""

import argparse
import asyncio
import os

import gradio as gr
from pydantic import BaseModel

from celery import Celery
from celery.result import AsyncResult

# Celery configuration
CELERY_BROKER_URL = os.environ["CELERY_BROKER_URL"]  # 'amqp://rabbitmq:rabbitmq@rabbit:5672/'
CELERY_RESULT_BACKEND = os.environ["CELERY_RESULT_BACKEND"]  # 'rpc://'
MAX_WAIT_TIME_SEC = 60  # seconds

# Initialize Celery
celeryapp = Celery(broker=CELERY_BROKER_URL, backend=CELERY_RESULT_BACKEND)
celeryapp.config_from_object('celeryconfig')


class ImageRegion(BaseModel):
    xtl: float
    ytl: float
    xbr: float
    ybr: float

# OCRMode is a string that indicates the mode of OCR processing.
#  "block" will detect lines and transcribe them, "line" will directly transcribe lines
# OCRMode = Literal["block", "line"]


class LineTranscription(BaseModel):
    text: str
    confidence: float
    polygon: list[list[float]]
    line_id: int

class OCREngineInfo(BaseModel):
    name: str
    version: str
    model: str
    model_version: str

class OCRResult(BaseModel):
    ocr_engine: OCREngineInfo
    lines: list[LineTranscription]



class OCRProxy:
    """Proxy to real workers."""
    def __init__(self):
        pass

    # async def transcribe(self, image_url: str, regions: Regions, mode: OCRMode = "block"):
    async def transcribe(self, image_url: str, regions: str) -> OCRResult:
        """Forwards request to task queue, and returns results when they are ready."""
        # regions is a json string which must be parsed as a list of ImageRegion

        # Validate `regions` input by parsing it with Pydantic
        try:
            if regions is None or regions is []:
                regions = []
            new_regions: list[ImageRegion] = []
            for region in regions:
                regions = ImageRegion.model_validate_json(region)
                new_regions.append(regions)
        except Exception as e:
            raise ValueError(f"Invalid regions format: {e}") from e
        
        
        # fake_answer = OCRResult(
        #     ocr_engine=OCREngineInfo(
        #         name="FakeOCR",
        #         version="1.0",
        #         model="fake_model",
        #         model_version="1.0"
        #     ).model_dump(),
        #     lines=[
        #         LineTranscription(
        #             text="Fake text",
        #             confidence=0.99,
        #             polygon=[[0, 0], [1, 0], [1, 1], [0, 1]],
        #             line_id=1
        #         ).model_dump()
        #     ]
        # ).model_dump()
        # await asyncio.sleep(2)  # Simulate network delay

        r = celeryapp.send_task('worker.run_ocr', args=(image_url, regions,), serializer="pickle")
        task_id = r.id
        print(f"Task ID: {task_id}")  # log task id

        # async wait loop
        result = AsyncResult(task_id, app=celeryapp)
        start_time = asyncio.get_event_loop().time()
        current_time = start_time
        while current_time - start_time < MAX_WAIT_TIME_SEC:
            if result.ready():
                # FIXME Validate result and send
                return result.get()
            if result.failed():
                return { "state" : result.state, "error": result.traceback }
            await asyncio.sleep(1)
            current_time = asyncio.get_event_loop().time()
        # Timeout
        print(f"Timeout waiting for task {task_id}")
        # FIXME return error
        return { "state" : "timeout", "error": "Timeout waiting for task" }


if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="OCR worker proxy")
    parser.add_argument("--concurrency_limit", default=1, type=int,
                        help="Maximum number of this event that can be running simultaneously")
    args = parser.parse_args()

    # Initialize Greeter with command-line arguments
    ocr_proxy = OCRProxy()
    api_fn = ocr_proxy.transcribe

    # Create a Gradio interface
    demo = gr.Interface(
        fn=api_fn,
        inputs=["text", "text"], #, gr.Radio()],
        outputs=[gr.JSON(label="OCR Result")],
        title="OCR API",
        description="A simple OCR API to transcribe images.",
        allow_flagging="never",
        concurrency_limit=args.concurrency_limit,
        api_name="transcribe",
    )
    # TODO add examples which will provide input and output examples.
    demo.launch(share=False)
