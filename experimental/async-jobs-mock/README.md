# Async Jobs Mock Spike

This spike validates a clean async API contract before integrating Celery workers.

## Features

- Swagger/OpenAPI via FastAPI (`/docs`).
- Service-specific submission routes:
  - `POST /v1/ocr/jobs`
  - `POST /v1/layout/jobs`
- Unified monitoring/result routes:
  - `GET /v1/jobs/{job_id}/events` (SSE)
  - `GET /v1/jobs/{job_id}/result`
  - `GET /v1/jobs/{job_id}/payload`
- Anonymous triage/fairness controls:
  - requester fingerprint (`X-Anonymous-Id` or `ip+ua` fallback)
  - per-requester in-flight cap
  - fairness penalty that lowers priority for noisy requesters

## Run locally

```bash
cd experimental/async-jobs-mock
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt
uv run uvicorn app:app --host 0.0.0.0 --port 8310 --reload
```

Then open:

- `http://127.0.0.1:8310/docs`

Frontend sample:

- `react-sample-client` quickstart: [`experimental/async-jobs-mock/react-sample-client/README.md`](react-sample-client/README.md)
- SSE wire protocol specification: [`experimental/async-jobs-mock/SSE_PROTOCOL.md`](SSE_PROTOCOL.md)

## Example flow

Submit OCR job:

```bash
curl -sS -X POST "http://127.0.0.1:8310/v1/ocr/jobs" \
  -H "Content-Type: application/json" \
  -H "X-Anonymous-Id: user-a" \
  -d '{
    "image_url": "https://example.org/fake-image.webp",
    "regions": [{"xtl": 0, "ytl": 0, "xbr": 100, "ybr": 100}],
    "simulated_duration_sec": 2.4,
    "simulated_steps": 4
  }'
```

Read events (replace `<job_id>`):

```bash
curl -N -sS "http://127.0.0.1:8310/v1/jobs/<job_id>/events"
```

Read result metadata:

```bash
curl -sS "http://127.0.0.1:8310/v1/jobs/<job_id>/result"
```

Read payload once completed:

```bash
curl -sS "http://127.0.0.1:8310/v1/jobs/<job_id>/payload"
```

## Notes for production migration

- Keep API contracts identical.
- Replace mock executor in `app.py` with Celery dispatch + worker callbacks.
- Replace in-memory store with Redis/PostgreSQL-backed job/event storage.
