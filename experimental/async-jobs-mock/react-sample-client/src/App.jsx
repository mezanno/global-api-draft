import { useEffect, useMemo, useRef, useState } from "react";
import { getJobPayload, getJobResult, openJobEvents, submitLayoutJob, submitOcrJob } from "./api";

const TERMINAL_EVENTS = new Set(["job.completed", "job.failed", "job.cancelled"]);

function safeParse(data) {
  try {
    return JSON.parse(data);
  } catch {
    return { raw: data };
  }
}

function nowIso() {
  return new Date().toISOString();
}

export default function App() {
  const [anonymousId, setAnonymousId] = useState("demo-user-a");
  const [serviceType, setServiceType] = useState("ocr");
  const [imageUrl, setImageUrl] = useState("https://example.org/fake-image.webp");
  const [regionsJson, setRegionsJson] = useState('[{"xtl":0,"ytl":0,"xbr":100,"ybr":100}]');
  const [simDuration, setSimDuration] = useState(2.4);
  const [simSteps, setSimSteps] = useState(4);
  const [currentJob, setCurrentJob] = useState(null);
  const [timeline, setTimeline] = useState([]);
  const [statusText, setStatusText] = useState("idle");
  const [resultData, setResultData] = useState(null);
  const [payloadData, setPayloadData] = useState(null);
  const [errorText, setErrorText] = useState("");
  const eventSourceRef = useRef(null);

  const canSubmit = useMemo(() => imageUrl.trim().length > 0, [imageUrl]);

  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  const appendTimeline = (eventName, data, id) => {
    setTimeline((items) => [...items, { at: nowIso(), eventName, id, data }]);
  };

  const closeStream = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  };

  const connectStream = (jobId) => {
    closeStream();
    const source = openJobEvents(jobId, {
      onEvent: (evt) => {
        const parsed = safeParse(evt.data);
        appendTimeline(evt.eventName, parsed, evt.id || "-");
        if (parsed?.status) {
          setStatusText(parsed.status);
        }
        if (TERMINAL_EVENTS.has(evt.eventName)) {
          closeStream();
        }
      },
      onError: () => {
        appendTimeline("job.stream_error", { message: "SSE stream interrupted, you can reconnect." }, "-");
      },
    });
    eventSourceRef.current = source;
  };

  const submit = async () => {
    setErrorText("");
    setResultData(null);
    setPayloadData(null);
    setTimeline([]);
    setStatusText("submitting");

    try {
      const payload =
        serviceType === "ocr"
          ? {
              image_url: imageUrl,
              regions: safeParse(regionsJson)?.raw ? [] : safeParse(regionsJson),
              simulated_duration_sec: Number(simDuration),
              simulated_steps: Number(simSteps),
            }
          : {
              image_url: imageUrl,
              auto_deskew: false,
              auto_bg_removal: true,
              auto_denoise: true,
              simulated_duration_sec: Number(simDuration),
              simulated_steps: Number(simSteps),
            };

      const created =
        serviceType === "ocr" ? await submitOcrJob(payload, anonymousId) : await submitLayoutJob(payload, anonymousId);
      setCurrentJob(created);
      setStatusText(created.status);
      appendTimeline("job.submitted", created, "-");
      connectStream(created.job_id);
    } catch (error) {
      setStatusText("error");
      setErrorText(error.message);
    }
  };

  const pollResult = async () => {
    if (!currentJob) return;
    setErrorText("");
    try {
      const result = await getJobResult(currentJob.job_id);
      setResultData(result);
      if (result.status) {
        setStatusText(result.status);
      }
      appendTimeline("job.result_polled", result, "-");
    } catch (error) {
      setErrorText(error.message);
    }
  };

  const fetchPayload = async () => {
    if (!currentJob) return;
    setErrorText("");
    try {
      const payload = await getJobPayload(currentJob.job_id);
      setPayloadData(payload);
      appendTimeline("job.payload_fetched", payload, "-");
    } catch (error) {
      setErrorText(error.message);
    }
  };

  return (
    <main className="page">
      <h1>Async Jobs React Sample</h1>
      <p className="hint">Submit OCR/Layout jobs, follow live SSE events, then fetch result and payload.</p>

      <section className="card">
        <div className="grid">
          <label>
            Anonymous Id
            <input value={anonymousId} onChange={(e) => setAnonymousId(e.target.value)} />
          </label>
          <label>
            Service
            <select value={serviceType} onChange={(e) => setServiceType(e.target.value)}>
              <option value="ocr">OCR</option>
              <option value="layout">Layout</option>
            </select>
          </label>
          <label className="full">
            Image URL
            <input value={imageUrl} onChange={(e) => setImageUrl(e.target.value)} />
          </label>
          <label className="full">
            OCR Regions JSON (used only for OCR)
            <textarea value={regionsJson} onChange={(e) => setRegionsJson(e.target.value)} rows={4} />
          </label>
          <label>
            Simulated Duration (sec)
            <input type="number" min="0.1" step="0.1" value={simDuration} onChange={(e) => setSimDuration(e.target.value)} />
          </label>
          <label>
            Simulated Steps
            <input type="number" min="1" step="1" value={simSteps} onChange={(e) => setSimSteps(e.target.value)} />
          </label>
        </div>
        <div className="actions">
          <button onClick={submit} disabled={!canSubmit}>
            Submit Job
          </button>
          <button onClick={pollResult} disabled={!currentJob}>
            Poll /result
          </button>
          <button onClick={fetchPayload} disabled={!currentJob}>
            Fetch /payload
          </button>
          <button onClick={() => currentJob && connectStream(currentJob.job_id)} disabled={!currentJob}>
            Reconnect SSE
          </button>
        </div>
      </section>

      <section className="card">
        <h2>Current Job</h2>
        <p>
          <strong>Status:</strong> <span className="chip">{statusText}</span>
        </p>
        <pre>{currentJob ? JSON.stringify(currentJob, null, 2) : "No submitted job yet."}</pre>
      </section>

      <section className="card">
        <h2>Timeline</h2>
        <div className="timeline">
          {timeline.length === 0 && <p className="hint">No events yet.</p>}
          {timeline.map((entry, index) => (
            <article key={`${entry.at}-${index}`} className="timeline-item">
              <div>
                <strong>{entry.eventName}</strong> <small>id={entry.id}</small>
              </div>
              <small>{entry.at}</small>
              <pre>{JSON.stringify(entry.data, null, 2)}</pre>
            </article>
          ))}
        </div>
      </section>

      <section className="card">
        <h2>/result response</h2>
        <pre>{resultData ? JSON.stringify(resultData, null, 2) : "No result polled yet."}</pre>
      </section>

      <section className="card">
        <h2>/payload response</h2>
        <pre>{payloadData ? JSON.stringify(payloadData, null, 2) : "No payload fetched yet."}</pre>
      </section>

      {errorText && (
        <section className="card error">
          <h2>Error</h2>
          <pre>{errorText}</pre>
        </section>
      )}
    </main>
  );
}
