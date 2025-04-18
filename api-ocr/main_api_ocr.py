"""
Interface to transcribe images, forwarding requests to a task queue.
"""

import argparse
import asyncio
import os
import json

import gradio as gr
from pydantic import BaseModel, AnyHttpUrl, ValidationError

from celery import Celery
from celery.result import AsyncResult

from datatypes import ImageRegion, ImageRegionListModel, LineTranscription, OCREngineInfo, OCRResult
import logging

# Initialize logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class OCRAPIAnswer(BaseModel):
    error: str | None = None
    result: OCRResult | None = None

    def __init__(self, **data):
        super().__init__(**data)
        if self.error and self.result:
            raise ValueError("Cannot have both error and result.")
        if not self.error and not self.result:
            raise ValueError("Must have either error or result.")
        if self.result:
            # Validate the result
            if not isinstance(self.result, OCRResult):
                raise ValueError("Result must be an instance of OCRResult.")
        if self.error:
            # Validate the error
            if not isinstance(self.error, str):
                raise ValueError("Error must be a string.")

class OCRProxy:
    """Proxy to real workers."""
    def __init__(self, celeryapp: Celery, task_timeout_sec: int = 30, task_initial_backoff_sec: float = 0.5, use_image_cache:bool = True):
        self._celeryapp = celeryapp

        self._task_timeout_sec = task_timeout_sec
        self._task_initial_backoff_sec = task_initial_backoff_sec

        self._use_image_cache = use_image_cache


    # async def transcribe(self, image_url: str, regions: Regions, mode: OCRMode = "block"):
    async def transcribe(self, image_url: AnyHttpUrl, regions: str) -> OCRAPIAnswer:
        """Forwards request to task queue, and returns results when they are ready."""
        # regions is a json string which must be parsed as a list of ImageRegion

        # Validate `image_url` input by parsing it with Pydantic
        try:
            _image_url = AnyHttpUrl(image_url)
        except ValidationError as e:
            return OCRAPIAnswer(
                error=f"Invalid image URL: {e}"
            ).model_dump()

        # If the URL starts with https?://openapi.bnf.fr/*, rewrite it to http://cache/openapi.bnf.fr/*
        if self._use_image_cache and image_url.startswith("https://openapi.bnf.fr/iiif/image/v3/"):
            image_url = image_url.replace("https://openapi.bnf.fr/iiif/image/v3/", "http://cache.mezanno.xyz/openapi.bnf.fr/iiif/image/v3/")

        # Validate `regions` input by parsing it with Pydantic
        try:
            # Parse the image regions from the JSON string
            if len(regions) < 2:
                regions = []
            else:
                regions = json.loads(regions)
                if regions is None or regions == []:
                    regions = []
                for region in regions:
                    region_ = ImageRegion.model_validate(region)
        except ValidationError as e:
            logger.error(f"Invalid regions format for '{regions}'")
            return OCRAPIAnswer(
                error=f"Invalid regions format: {e}"
            ).model_dump()
        
        r = self._celeryapp.send_task('worker.run_ocr', args=(image_url, regions,))
        task_id = r.id

        # async wait loop
        result = AsyncResult(task_id, app=self._celeryapp)
        backoff = self._task_initial_backoff_sec
        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < self._task_timeout_sec*1000:
            if result.ready():
                raw_result = result.get(timeout=0.1)  # this should not wait because the result must be ready()
                # Wrap the result to ease result parsing in client
                return {"result": raw_result}
            if result.failed():
                return OCRAPIAnswer(
                    error=f"Task {task_id} failed: {result.result}"
                ).model_dump()
            
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, self._task_timeout_sec/10)  # Exponential backoff with a cap
        
        # Timeout
        print(f"Timeout waiting for task {task_id} after {self._task_timeout_sec} seconds.")
        # Cancel the task
        self._celeryapp.control.revoke(task_id, terminate=True) # signal='SIGKILL'
        print(f"Task {task_id} cancelled because of timeout after {self._task_timeout_sec} seconds.")
        return OCRAPIAnswer(
            error=f"Timeout waiting for task {task_id} after {self._task_timeout_sec} seconds."
        ).model_dump()


def main():
    # Default configuration
    GRADIO_SERVER_PORT = os.environ.get("GRADIO_SERVER_PORT", 7860)
    GRADIO_SERVER_NAME = os.environ.get("GRADIO_SERVER_NAME", "0.0.0.0")
    GRADIO_CONCURRENCY_LIMIT = os.environ.get("GRADIO_CONCURRENCY_LIMIT", 1)
    GRADIO_ROOT_PATH = os.environ.get("GRADIO_ROOT_PATH", "")
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
    parser.add_argument("--gradio_root_path", default=GRADIO_ROOT_PATH, type=str,
                        help="Root path for Gradio server")
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

    example0 = [ImageRegion(xtl=0.0, ytl=0.0, xbr=100.0, ybr=100.0), ImageRegion(xtl=0, ytl=0, xbr=150, ybr=150)]
    gradio_examples = [
        ["https://picsum.photos/200/300", ImageRegionListModel.dump_json(example0).decode("utf-8")],
        ["https://picsum.photos/200/300", '[{"xtl": 0.0, "ytl": 0.0, "xbr": 100.0, "ybr": 100.0}]'],
        ["https://picsum.photos/100", '[{"xtl": 0.5, "ytl": 0.6, "xbr": 0.7, "ybr": 0.8}]'],
        ["https://cache.mezanno.xyz/openapi.bnf.fr/iiif/image/v3/ark:/12148/bd6t543045578/f5/full/max/0/default.webp",
          '[{"xtl": 0.0, "ytl": 0.0, "xbr": 100.0, "ybr": 100.0}]'],
        ["https://cache.mezanno.xyz/openapi.bnf.fr/iiif/image/v3/ark:/12148/bd6t543045578/f10/full/max/0/default.webp",
          '[]'],
        ["https://cache.mezanno.xyz/openapi.bnf.fr/iiif/image/v3/ark:/12148/bd6t543045578/f100/full/max/0/default.webp", ""]
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
    logger.info(f"Gradio server will run on {args.gradio_server_name}:{args.gradio_server_port}")
    logger.info(f"Gradio concurrency limit: {args.gradio_concurrency_limit}")
    logger.info(f"Celery broker URL: {args.celery_broker_url}")
    logger.info(f"Celery result backend URL: {args.celery_result_backend}")
    logger.info(f"Task timeout: {args.task_timeout_sec} seconds")
    logger.info(f"Task initial backoff: {args.task_initial_backoff_sec} seconds")

    # Launch the Gradio app
    demo.launch(share=False, root_path=args.gradio_root_path)

if __name__ == "__main__":
    main()
