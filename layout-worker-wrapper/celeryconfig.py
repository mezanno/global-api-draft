from kombu import Queue

task_queues = (
    Queue("layout"),
    Queue("ocr"),
)

task_routes = {
    "layout.*": {"queue": "layout"},
    "ocr.*": {"queue": "ocr"},
}

task_default_queue = "default"

