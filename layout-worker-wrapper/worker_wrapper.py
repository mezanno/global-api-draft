from fastapi import FastAPI
from fastapi import HTTPException
import uvicorn
import httpx
import os

from celery import Celery
from celery.result import AsyncResult

app = FastAPI()

CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "amqp://guest:guest@rabbitmq:5672")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "rpc://")

celeryapp = Celery(broker=CELERY_BROKER_URL, backend=CELERY_RESULT_BACKEND)
celeryapp.config_from_object("celeryconfig", silent=True)


@app.get("/layout")
async def layout_enqueue(
    image_url: str,
    auto_deskew: bool = False,
    auto_bg_removal: bool = True,
    auto_denoise: bool = True,
    text_x_height_pixels: int = -1,
):
    r = celeryapp.send_task(
        "layout.run_layout",
        kwargs={
            "image_url": image_url,
            "auto_deskew": auto_deskew,
            "auto_bg_removal": auto_bg_removal,
            "auto_denoise": auto_denoise,
            "text_x_height_pixels": text_x_height_pixels,
        },
        queue="layout",
    )
    return {"task_id": r.id}


@app.get("/layout/result")
async def layout_result(task_id: str):
    if not task_id:
        raise HTTPException(status_code=400, detail="task_id is required")

    result = AsyncResult(task_id, app=celeryapp)
    payload: dict = {"task_id": task_id, "state": result.state, "ready": result.ready()}

    if result.successful():
        payload["result"] = result.get(timeout=0.1)
    elif result.failed():
        payload["error"] = str(result.result)

    return payload
    


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
