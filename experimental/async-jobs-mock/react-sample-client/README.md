# React Sample Client (Vite + React)

This sample frontend demonstrates how to consume the async jobs API in practice:

- submit OCR or layout jobs
- follow live updates with SSE
- use polling fallback via `/result`
- fetch final payload via `/payload`

## Prerequisites

- Node.js 20+
- `uv` for running the backend mock API

## 1) Run the backend mock API

From repo root:

```bash
cd experimental/async-jobs-mock
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt
uv run uvicorn app:app --host 0.0.0.0 --port 8310 --reload
```

## 2) Run the React sample client

Open another terminal:

```bash
cd experimental/async-jobs-mock/react-sample-client
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

## What the UI demonstrates

- `X-Anonymous-Id` input to simulate different users/fairness behavior
- OCR/Layout submission forms
- live timeline from `GET /v1/jobs/{job_id}/events`
- manual polling button for `GET /v1/jobs/{job_id}/result`
- payload button for `GET /v1/jobs/{job_id}/payload`

## Scenario A: Happy path with SSE

1. Choose service `ocr`.
2. Keep the default image URL and regions.
3. Click **Submit Job**.
4. Observe event sequence in timeline:
   - `job.accepted`
   - `job.queued`
   - `job.started`
   - `job.progress`
   - `job.completed`
5. Click **Fetch /payload** to display final result data.

## Scenario B: Polling fallback

1. Submit a `layout` job.
2. Ignore live events or disconnect stream.
3. Click **Poll /result** repeatedly until `ready: true`.
4. Click **Fetch /payload**.

## Scenario C: Fairness hint

1. Open two browser tabs.
2. Use `demo-user-a` in tab A and `demo-user-b` in tab B.
3. Submit several jobs quickly from both tabs.
4. Compare timelines to observe round-robin style progression.

## Notes

- Vite dev server proxies `/v1` and `/healthz` to `http://127.0.0.1:8310`.
- To target another backend, set `VITE_API_BASE_URL` before `npm run dev`.
