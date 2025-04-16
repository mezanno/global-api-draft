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
    def __init__(self, celeryapp: Celery, task_timeout_sec: int = 30, task_initial_backoff_sec: float = 0.5):
        self._celeryapp = celeryapp

        self._task_timeout_sec = task_timeout_sec
        self._task_initial_backoff_sec = task_initial_backoff_sec

        self._ocr_engine = None
        self._ocr_engine_info = None


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

        r = self._celeryapp.send_task('worker.run_ocr', args=(image_url, regions,), serializer="pickle")
        task_id = r.id
        print(f"Task ID: {task_id}")  # log task id

        # async wait loop
        result = AsyncResult(task_id, app=self._celeryapp)
        backoff = self._task_initial_backoff_sec
        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < self._task_timeout_sec*1000:
            if result.ready():
                # FIXME Validate result and send
                return result.get(timeout=0.1)  # this should not wait because the result must be ready()
            if result.failed():
                return { "state" : result.state, "error": result.traceback }
            
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, self._task_timeout_sec/10)  # Exponential backoff with a cap
        
        # Timeout
        print(f"Timeout waiting for task {task_id} after {self._task_timeout_sec} seconds.")
        # TODO cancel the task
        # TODO log the error
        # FIXME return error
        return { "state" : "timeout", "error": f"Timeout waiting for task after {self._task_timeout_sec} seconds." }


if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="PERO OCR worker proxy")
    parser.add_argument("--gradio_concurrency_limit", default=1, type=int,
                        help="Maximum number of this event that can be running simultaneously")
    parser.add_argument("--task_timeout_sec", default=30, type=int,
                        help="Timeout for task in seconds")
    parser.add_argument("--task_initial_backoff_sec", default=0.5, type=float,
                        help="Initial backoff for task in seconds")
    # TODO add parameters for OCR model (path, name, version…)
    args = parser.parse_args()

    # Set up Celery
    # Celery configuration
    # TODO enable cmdline arguments for these
    CELERY_BROKER_URL = os.environ["CELERY_BROKER_URL"]  # 'amqp://rabbitmq:rabbitmq@rabbit:5672/'
    CELERY_RESULT_BACKEND = os.environ["CELERY_RESULT_BACKEND"]  # 'rpc://'

    # Initialize Celery
    celeryapp = Celery(broker=CELERY_BROKER_URL, backend=CELERY_RESULT_BACKEND)
    celeryapp.config_from_object('celeryconfig')


    # Initialize Greeter with command-line arguments
    ocr_proxy = OCRProxy(
        task_timeout_sec=args.task_timeout_sec,
        task_initial_backoff_sec=args.task_initial_backoff_sec,
        celeryapp=celeryapp,
        )
    api_fn = ocr_proxy.transcribe

    # Create a Gradio interface
    demo = gr.Interface(
        fn=api_fn,
        inputs=["text", "text"], #, gr.Radio()],
        outputs=[gr.JSON(label="OCR Result")],
        title="OCR API",
        description="A simple OCR API to transcribe images.",
        allow_flagging="never",
        concurrency_limit=args.gradio_concurrency_limit,
        api_name="transcribe",
    )
    # TODO add examples which will provide input and output examples.
    demo.launch(share=False)
