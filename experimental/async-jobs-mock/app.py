import asyncio
import json
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field
from starlette.responses import StreamingResponse


TERMINAL_STATUSES = {"completed", "failed", "cancelled"}


def format_sse(*, event: str, data: dict[str, Any], event_id: int | None = None) -> str:
    lines: list[str] = []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event}")
    lines.append(f"data: {json.dumps(data)}")
    return "\n".join(lines) + "\n\n"


class OCRSubmitRequest(BaseModel):
    image_url: str
    regions: list[dict[str, float]] = Field(default_factory=list)
    simulated_duration_sec: float = 2.0
    simulated_steps: int = 4


class LayoutSubmitRequest(BaseModel):
    image_url: str
    auto_deskew: bool = False
    auto_bg_removal: bool = True
    auto_denoise: bool = True
    simulated_duration_sec: float = 1.2
    simulated_steps: int = 3


class JobEnvelope(BaseModel):
    job_id: str
    service: str
    status: str
    priority: int
    created_at: float
    events_url: str
    result_url: str


@dataclass
class JobRecord:
    job_id: str
    service: str
    requester_id: str
    payload: dict[str, Any]
    priority: int
    created_at: float
    status: str = "accepted"
    result: dict[str, Any] | None = None
    error: str | None = None


@dataclass
class EventRecord:
    id: int
    event: str
    data: dict[str, Any]
    timestamp: float = field(default_factory=time.time)


class TriagePolicy:
    def __init__(self, per_requester_inflight_limit: int = 2, heavy_penalty_threshold: int = 4) -> None:
        self.per_requester_inflight_limit = per_requester_inflight_limit
        self.heavy_penalty_threshold = heavy_penalty_threshold
        self.pending_count_by_requester: dict[str, int] = defaultdict(int)
        self.inflight_count_by_requester: dict[str, int] = defaultdict(int)

    def evaluate(self, requester_id: str, simulated_duration_sec: float) -> tuple[bool, int, int]:
        pending = self.pending_count_by_requester[requester_id]
        inflight = self.inflight_count_by_requester[requester_id]
        if pending + inflight >= 20:
            return False, 0, 30

        base_priority = 10 if simulated_duration_sec > 2.5 else 5
        fairness_penalty = (pending + inflight) // self.heavy_penalty_threshold
        priority = min(base_priority + fairness_penalty, 20)
        return True, priority, 0


class JobStore:
    def __init__(self) -> None:
        self.jobs: dict[str, JobRecord] = {}
        self.events: dict[str, list[EventRecord]] = defaultdict(list)
        self.subscribers: dict[str, set[asyncio.Queue[EventRecord]]] = defaultdict(set)
        self.next_event_id: dict[str, int] = defaultdict(lambda: 1)
        self.lock = asyncio.Lock()

    async def create_job(self, job: JobRecord) -> None:
        async with self.lock:
            self.jobs[job.job_id] = job
        await self.append_event(
            job.job_id,
            "job.accepted",
            {"job_id": job.job_id, "service": job.service, "status": "accepted", "priority": job.priority},
        )

    async def append_event(self, job_id: str, event: str, data: dict[str, Any]) -> EventRecord:
        async with self.lock:
            eid = self.next_event_id[job_id]
            self.next_event_id[job_id] += 1
            rec = EventRecord(id=eid, event=event, data=data)
            self.events[job_id].append(rec)
            listeners = list(self.subscribers[job_id])

        for queue in listeners:
            queue.put_nowait(rec)
        return rec

    async def replay_events(self, job_id: str, last_event_id: int) -> list[EventRecord]:
        async with self.lock:
            source = self.events.get(job_id, [])
            return [ev for ev in source if ev.id > last_event_id]

    async def subscribe(self, job_id: str) -> asyncio.Queue[EventRecord]:
        queue: asyncio.Queue[EventRecord] = asyncio.Queue()
        async with self.lock:
            self.subscribers[job_id].add(queue)
        return queue

    async def unsubscribe(self, job_id: str, queue: asyncio.Queue[EventRecord]) -> None:
        async with self.lock:
            self.subscribers[job_id].discard(queue)


class FairScheduler:
    def __init__(self, store: JobStore, triage: TriagePolicy, concurrency: int = 3) -> None:
        self.store = store
        self.triage = triage
        self.concurrency = concurrency
        self.pending_by_requester: dict[str, deque[str]] = defaultdict(deque)
        self.round_robin_order: deque[str] = deque()
        self.active_workers = 0
        self.cv = asyncio.Condition()

    async def enqueue(self, job: JobRecord) -> None:
        async with self.cv:
            rid = job.requester_id
            self.pending_by_requester[rid].append(job.job_id)
            self.triage.pending_count_by_requester[rid] += 1
            if rid not in self.round_robin_order:
                self.round_robin_order.append(rid)
            await self.store.append_event(
                job.job_id,
                "job.queued",
                {"job_id": job.job_id, "status": "queued", "priority": job.priority},
            )
            self.cv.notify_all()

    async def run(self) -> None:
        while True:
            async with self.cv:
                await self.cv.wait_for(self._can_dispatch)
                job_id = self._select_next_job()
                if job_id is None:
                    continue
                self.active_workers += 1
            asyncio.create_task(self._execute(job_id))

    def _can_dispatch(self) -> bool:
        return self.active_workers < self.concurrency and any(self.pending_by_requester.values())

    def _select_next_job(self) -> str | None:
        for _ in range(len(self.round_robin_order)):
            rid = self.round_robin_order[0]
            self.round_robin_order.rotate(-1)
            if not self.pending_by_requester[rid]:
                continue
            if self.triage.inflight_count_by_requester[rid] >= self.triage.per_requester_inflight_limit:
                continue
            job_id = self.pending_by_requester[rid].popleft()
            self.triage.pending_count_by_requester[rid] -= 1
            self.triage.inflight_count_by_requester[rid] += 1
            return job_id
        return None

    async def _execute(self, job_id: str) -> None:
        try:
            job = self.store.jobs[job_id]
            job.status = "started"
            await self.store.append_event(
                job.job_id, "job.started", {"job_id": job.job_id, "status": "started", "priority": job.priority}
            )
            total_steps = max(int(job.payload["simulated_steps"]), 1)
            total_duration = float(job.payload["simulated_duration_sec"])
            step_sleep = max(total_duration / total_steps, 0.05)
            for step in range(total_steps):
                await asyncio.sleep(step_sleep)
                progress = round(((step + 1) / total_steps) * 100.0, 1)
                job.status = "progress"
                await self.store.append_event(
                    job.job_id,
                    "job.progress",
                    {"job_id": job.job_id, "status": "progress", "progress": progress},
                )
            job.status = "completed"
            job.result = {
                "service": job.service,
                "message": f"Mock {job.service} processing finished.",
                "input": job.payload,
                "computed_at": time.time(),
            }
            await self.store.append_event(
                job.job_id,
                "job.completed",
                {
                    "job_id": job.job_id,
                    "status": "completed",
                    "result_url": f"/v1/jobs/{job.job_id}/result",
                    "payload_url": f"/v1/jobs/{job.job_id}/payload",
                },
            )
        except Exception as exc:
            job = self.store.jobs[job_id]
            job.status = "failed"
            job.error = str(exc)
            await self.store.append_event(
                job.job_id, "job.failed", {"job_id": job.job_id, "status": "failed", "error": job.error}
            )
        finally:
            rid = self.store.jobs[job_id].requester_id
            self.triage.inflight_count_by_requester[rid] = max(0, self.triage.inflight_count_by_requester[rid] - 1)
            async with self.cv:
                self.active_workers = max(0, self.active_workers - 1)
                self.cv.notify_all()


app = FastAPI(
    title="Async Jobs Mock API",
    version="0.1.0",
    description="Mock-first async API with triage/fairness and SSE replay support.",
)
store = JobStore()
triage = TriagePolicy()
scheduler = FairScheduler(store=store, triage=triage, concurrency=3)


def requester_fingerprint(request: Request, anonymous_id: str | None) -> str:
    if anonymous_id:
        return f"anon:{anonymous_id}"
    client_host = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "na")
    return f"ipua:{client_host}:{hash(user_agent) % 10_000}"


def job_response(request: Request, job: JobRecord) -> JobEnvelope:
    return JobEnvelope(
        job_id=job.job_id,
        service=job.service,
        status=job.status,
        priority=job.priority,
        created_at=job.created_at,
        events_url=f"{request.url.scheme}://{request.url.netloc}/v1/jobs/{job.job_id}/events",
        result_url=f"{request.url.scheme}://{request.url.netloc}/v1/jobs/{job.job_id}/result",
    )


async def submit_job(request: Request, service: str, payload: dict[str, Any], anonymous_id: str | None) -> JobEnvelope:
    requester_id = requester_fingerprint(request, anonymous_id)
    accepted, priority, retry_after = triage.evaluate(requester_id, float(payload["simulated_duration_sec"]))
    if not accepted:
        raise HTTPException(status_code=429, detail=f"Queue is saturated. Retry after {retry_after} seconds.")
    job = JobRecord(
        job_id=f"job_{uuid.uuid4().hex[:16]}",
        service=service,
        requester_id=requester_id,
        payload=payload,
        priority=priority,
        created_at=time.time(),
    )
    await store.create_job(job)
    await scheduler.enqueue(job)
    return job_response(request, job)


@app.on_event("startup")
async def startup_event() -> None:
    asyncio.create_task(scheduler.run())


@app.get("/healthz")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/ocr/jobs", status_code=202, response_model=JobEnvelope)
async def submit_ocr_job(
    body: OCRSubmitRequest, request: Request, x_anonymous_id: str | None = Header(default=None)
) -> JobEnvelope:
    return await submit_job(request, "ocr", body.model_dump(), x_anonymous_id)


@app.post("/v1/layout/jobs", status_code=202, response_model=JobEnvelope)
async def submit_layout_job(
    body: LayoutSubmitRequest, request: Request, x_anonymous_id: str | None = Header(default=None)
) -> JobEnvelope:
    return await submit_job(request, "layout", body.model_dump(), x_anonymous_id)


@app.get("/v1/jobs/{job_id}/result")
async def get_job_result(job_id: str) -> dict[str, Any]:
    job = store.jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Unknown job_id.")
    if job.status not in TERMINAL_STATUSES:
        return {"job_id": job.job_id, "status": job.status, "ready": False}
    return {
        "job_id": job.job_id,
        "service": job.service,
        "status": job.status,
        "ready": True,
        "payload_url": f"/v1/jobs/{job_id}/payload",
        "error": job.error,
    }


@app.get("/v1/jobs/{job_id}/payload")
async def get_job_payload(job_id: str) -> dict[str, Any]:
    job = store.jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Unknown job_id.")
    if job.status != "completed":
        raise HTTPException(status_code=409, detail=f"Job is not completed (status={job.status}).")
    return {"job_id": job.job_id, "result": job.result}


@app.get("/v1/jobs/{job_id}/events")
async def stream_job_events(job_id: str, request: Request, last_event_id: str | None = Header(default=None)) -> Any:
    job = store.jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Unknown job_id.")
    try:
        replay_after = int(last_event_id or "0")
    except ValueError:
        replay_after = 0

    async def event_gen() -> Any:
        replay = await store.replay_events(job_id, replay_after)
        for ev in replay:
            yield format_sse(event=ev.event, data=ev.data, event_id=ev.id)

        queue = await store.subscribe(job_id)
        try:
            heartbeat_sec = 15
            while True:
                if await request.is_disconnected():
                    break
                try:
                    ev = await asyncio.wait_for(queue.get(), timeout=heartbeat_sec)
                    yield format_sse(event=ev.event, data=ev.data, event_id=ev.id)
                except asyncio.TimeoutError:
                    yield format_sse(event="job.heartbeat", data={"job_id": job_id, "status": "alive"})
        finally:
            await store.unsubscribe(job_id, queue)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
