# SSE Wire Protocol Specification

This document specifies the wire protocol for the async job events stream:

- `GET /v1/jobs/{job_id}/events`
- Content type: `text/event-stream`

It describes current behavior implemented in `app.py`.

## 1. Transport and framing

- The endpoint returns a long-lived HTTP response with media type `text/event-stream`.
- Stream content is UTF-8 text.
- Each SSE frame is formatted as:
  - optional `id: <event_id>`
  - `event: <event_name>`
  - `data: <json_object_on_single_line>`
  - blank line terminator

Canonical frame:

```text
id: 7
event: job.completed
data: {"job_id":"job_abc","status":"completed","result_url":"/v1/jobs/job_abc/result","payload_url":"/v1/jobs/job_abc/payload"}

```

## 2. Request contract

### Endpoint

`GET /v1/jobs/{job_id}/events`

### Headers

- Optional: `Last-Event-ID: <integer>`
  - If present and valid, server replays retained events with `id > Last-Event-ID`.
  - If missing or invalid, replay starts at beginning of retained event history.

### Errors

- `404` when `job_id` is unknown.

## 3. Event ordering and delivery semantics

- Event IDs are strictly monotonic per job (`1, 2, 3, ...`).
- Ordering is preserved per job.
- Replay events are sent before live events.
- Delivery semantics are at-least-once with replay support from retained in-memory events.

## 4. Event catalog

All `data:` payloads are JSON objects.

### `job.accepted`

```json
{
  "job_id": "job_x",
  "service": "ocr|layout",
  "status": "accepted",
  "priority": 5
}
```

### `job.queued`

```json
{
  "job_id": "job_x",
  "status": "queued",
  "priority": 5
}
```

### `job.started`

```json
{
  "job_id": "job_x",
  "status": "started",
  "priority": 5
}
```

### `job.progress`

```json
{
  "job_id": "job_x",
  "status": "progress",
  "progress": 33.3
}
```

- `progress` is a percentage float in `[0, 100]`.

### `job.completed`

```json
{
  "job_id": "job_x",
  "status": "completed",
  "result_url": "/v1/jobs/job_x/result",
  "payload_url": "/v1/jobs/job_x/payload"
}
```

- `payload_url` is included so SSE clients can fetch final payload directly.

### `job.failed`

```json
{
  "job_id": "job_x",
  "status": "failed",
  "error": "error detail"
}
```

### `job.cancelled`

Reserved terminal event type for future use.

### `job.heartbeat`

```json
{
  "job_id": "job_x",
  "status": "alive"
}
```

## 5. Heartbeat behavior

- Server emits heartbeat when no event is produced during the heartbeat interval.
- Current interval in mock implementation: 15 seconds.
- Heartbeat frame uses `event: job.heartbeat`.

## 6. Stream lifecycle

- Stream may stay open after terminal events until client disconnects.
- Recommended client behavior:
  1. Subscribe to events.
  2. Stop on terminal event (`job.completed`, `job.failed`, `job.cancelled`).
  3. Fetch result metadata and/or payload URL.

## 7. Reconnection guidance

- Track last seen event ID.
- On reconnect, send `Last-Event-ID`.
- Client should be tolerant to duplicate events (dedupe by `id`).
- If stream is unavailable, fallback to polling:
  - `GET /v1/jobs/{job_id}/result`
  - then `GET /v1/jobs/{job_id}/payload` when ready.

## 8. End-to-end example stream

```text
id: 1
event: job.accepted
data: {"job_id":"job_1","service":"layout","status":"accepted","priority":5}

id: 2
event: job.queued
data: {"job_id":"job_1","status":"queued","priority":5}

id: 3
event: job.started
data: {"job_id":"job_1","status":"started","priority":5}

id: 4
event: job.progress
data: {"job_id":"job_1","status":"progress","progress":33.3}

id: 5
event: job.progress
data: {"job_id":"job_1","status":"progress","progress":66.7}

id: 6
event: job.progress
data: {"job_id":"job_1","status":"progress","progress":100.0}

id: 7
event: job.completed
data: {"job_id":"job_1","status":"completed","result_url":"/v1/jobs/job_1/result","payload_url":"/v1/jobs/job_1/payload"}

```
