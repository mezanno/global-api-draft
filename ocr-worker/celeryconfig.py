from kombu import Queue

# Queues (explicitly declared so workers can bind selectively via `-Q`)
task_queues = (
    Queue("ocr"),
    Queue("layout"),
)

# Route tasks by their canonical name prefix.
task_routes = {
    "ocr.*": {"queue": "ocr"},
    "layout.*": {"queue": "layout"},
}

# Keep defaults explicit (helps avoid surprises when tasks are misnamed).
task_default_queue = "default"
