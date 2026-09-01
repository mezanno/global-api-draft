const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

async function parseJson(response) {
  const text = await response.text();
  try {
    return text ? JSON.parse(text) : {};
  } catch {
    return { raw: text };
  }
}

export async function submitOcrJob(payload, anonymousId) {
  const response = await fetch(`${API_BASE}/v1/ocr/jobs`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(anonymousId ? { "X-Anonymous-Id": anonymousId } : {}),
    },
    body: JSON.stringify(payload),
  });
  const data = await parseJson(response);
  if (!response.ok) {
    throw new Error(data?.detail || "Failed to submit OCR job.");
  }
  return data;
}

export async function submitLayoutJob(payload, anonymousId) {
  const response = await fetch(`${API_BASE}/v1/layout/jobs`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(anonymousId ? { "X-Anonymous-Id": anonymousId } : {}),
    },
    body: JSON.stringify(payload),
  });
  const data = await parseJson(response);
  if (!response.ok) {
    throw new Error(data?.detail || "Failed to submit layout job.");
  }
  return data;
}

export async function getJobResult(jobId) {
  const response = await fetch(`${API_BASE}/v1/jobs/${jobId}/result`);
  const data = await parseJson(response);
  if (!response.ok) {
    throw new Error(data?.detail || "Failed to retrieve job result.");
  }
  return data;
}

export async function getJobPayload(jobId) {
  const response = await fetch(`${API_BASE}/v1/jobs/${jobId}/payload`);
  const data = await parseJson(response);
  if (!response.ok) {
    throw new Error(data?.detail || "Failed to retrieve payload.");
  }
  return data;
}

export function openJobEvents(jobId, handlers = {}) {
  const eventsUrl = `${API_BASE}/v1/jobs/${jobId}/events`;
  const source = new EventSource(eventsUrl);

  source.onmessage = (event) => {
    handlers.onEvent?.({ type: "message", eventName: "message", data: event.data, id: event.lastEventId });
  };

  source.onerror = (error) => {
    handlers.onError?.(error);
  };

  const eventNames = [
    "job.accepted",
    "job.queued",
    "job.started",
    "job.progress",
    "job.completed",
    "job.failed",
    "job.cancelled",
    "job.heartbeat",
  ];

  for (const eventName of eventNames) {
    source.addEventListener(eventName, (event) => {
      handlers.onEvent?.({ type: "named", eventName, data: event.data, id: event.lastEventId });
    });
  }

  return source;
}
