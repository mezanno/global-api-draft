"""
Interface to transcribe images, forwarding requests to a task queue.
"""

import argparse
import asyncio
import os

import gradio as gr
from pydantic import BaseModel, AnyHttpUrl

from celery import Celery
from celery.result import AsyncResult


class ImageRegion(BaseModel):
    xtl: float|int
    ytl: float|int
    xbr: float|int
    ybr: float|int
# Sample list of ImageRegion objects: 
# [{"xtl": 0.0, "ytl": 0.0, "xbr": 100.0, "ybr": 100.0}, {"xtl": 0.5, "ytl": 0.6, "xbr": 0.7, "ybr": 0.8}]

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
    async def transcribe(self, image_url: AnyHttpUrl, regions: str) -> OCRResult:
        """Forwards request to task queue, and returns results when they are ready."""
        # regions is a json string which must be parsed as a list of ImageRegion

        # Validate `image_url` input by parsing it with Pydantic
        # try:
        #     image_url = AnyHttpUrl(image_url)
        # except Exception as e:
        #     raise ValueError(f"Invalid image URL: {e}") from e

        # # Validate `regions` input by parsing it with Pydantic
        # try:
        #     if regions is None or regions is []:
        #         regions = []
        #     new_regions: list[ImageRegion] = []
        #     for region in regions:
        #         region_ = ImageRegion.model_validate_json(region)
        #         new_regions.append(region_)
        # except Exception as e:
        #     print(f"Invalid regions format for '{regions}'")
        #     raise ValueError(f"Invalid regions format: {e}") from e
        
        
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

        r = self._celeryapp.send_task('worker.run_ocr', args=(image_url, regions,))
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


def main():
    # Default configuration
    GRADIO_SERVER_PORT = os.environ.get("GRADIO_SERVER_PORT", 7860)
    GRADIO_SERVER_NAME = os.environ.get("GRADIO_SERVER_NAME", "0.0.0.0")
    GRADIO_CONCURRENCY_LIMIT = os.environ.get("GRADIO_CONCURRENCY_LIMIT", 1)
    TASK_TIMEOUT_SEC = os.environ.get("TASK_TIMEOUT_SEC", 30)
    TASK_INITIAL_BACKOFF_SEC = os.environ.get("TASK_INITIAL_BACKOFF_SEC", 0.5)
    CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "amqp://rabbitmq:rabbitmq@rabbit:5672/")
    CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "rpc://")
    # TODO add parameters for OCR model (path, name, version…)

    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="PERO OCR worker proxy")
    parser.add_argument("--gradio_concurrency_limit", default=GRADIO_CONCURRENCY_LIMIT, type=int,
                        help="Maximum number of this event that can be running simultaneously")
    parser.add_argument("--gradio_server_port", default=GRADIO_SERVER_PORT, type=int,
                        help="Port for Gradio server")
    parser.add_argument("--gradio_server_name", default=GRADIO_SERVER_NAME, type=str,
                        help="Name for Gradio server")
    parser.add_argument("--task_timeout_sec", default=TASK_TIMEOUT_SEC, type=int,
                        help="Timeout for task in seconds")
    parser.add_argument("--task_initial_backoff_sec", default=TASK_INITIAL_BACKOFF_SEC, type=float,
                        help="Initial backoff for task in seconds")
    parser.add_argument("--celery_broker_url", default=CELERY_BROKER_URL, type=str,
                        help="Celery broker URL")
    parser.add_argument("--celery_result_backend", default=CELERY_RESULT_BACKEND, type=str,
                        help="Celery result backend URL")
    
    
    args = parser.parse_args()

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

    gradio_examples = [
        ["https://picsum.photos/200/300", '[{"xtl": 0.0, "ytl": 0.0, "xbr": 100.0, "ybr": 100.0}]'],
        ["https://picsum.photos/100", '[{"xtl": 0.5, "ytl": 0.6, "xbr": 0.7, "ybr": 0.8}]'],
        ["https://cache.mezanno.xyz/openapi.bnf.fr/iiif/image/v3/ark:/12148/bd6t543045578/f5/full/max/0/default.webp",
          '[{"xtl": 0.0, "ytl": 0.0, "xbr": 100.0, "ybr": 100.0}]'],
        # Add more example images and regions as needed
    ]

    demo = gr.Interface(
        fn=api_fn,
        inputs=["text", "text"], #, gr.Radio()],
        outputs=[gr.JSON(label="OCR Result")],
        title="OCR API",
        description="A simple OCR API to transcribe images.",
        allow_flagging="never",
        concurrency_limit=args.gradio_concurrency_limit,
        api_name="transcribe",
        examples=gradio_examples,
    )
    # Print some debug info
    print(f"Gradio server will run on {args.gradio_server_name}:{args.gradio_server_port}")
    print(f"Gradio concurrency limit: {args.gradio_concurrency_limit}")
    print(f"Celery broker URL: {args.celery_broker_url}")
    print(f"Celery result backend URL: {args.celery_result_backend}")
    print(f"Task timeout: {args.task_timeout_sec} seconds")
    print(f"Task initial backoff: {args.task_initial_backoff_sec} seconds")

    # Launch the Gradio app
    demo.launch(share=False)

if __name__ == "__main__":
    main()
