import os

import httpx
from celery import Celery


CELERY_BROKER_URL = os.environ["CELERY_BROKER_URL"]
CELERY_RESULT_BACKEND = os.environ["CELERY_RESULT_BACKEND"]

LAYOUT_SERVICE_URL = os.environ.get("LAYOUT_SERVICE_URL", "http://layout-worker:8000/imgproc/layout")


celery = Celery("layout_worker", broker=CELERY_BROKER_URL, backend=CELERY_RESULT_BACKEND)
celery.config_from_object("celeryconfig")


@celery.task(name="layout.run_layout")
def run_layout(
    image_url: str,
    auto_deskew: bool = False,
    auto_bg_removal: bool = True,
    auto_denoise: bool = True,
    text_x_height_pixels: int = -1,
) -> dict:
    # Note: the current layout C++ backend only consumes raw bytes at /imgproc/layout.
    # The additional parameters are accepted for forward-compat and are currently unused.
    timeout = httpx.Timeout(connect=10.0, read=60.0, write=60.0, pool=10.0)
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        r = client.get(image_url)
        r.raise_for_status()

        layout_r = client.post(LAYOUT_SERVICE_URL, content=r.content)
        layout_r.raise_for_status()

        return layout_r.json()

