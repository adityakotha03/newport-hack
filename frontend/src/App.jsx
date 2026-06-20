import { useEffect, useRef, useState } from "react";
import Logo from "./components/Logo.jsx";
import Landing from "./Landing.jsx";
import { analyze, generate, getJob, mediaUrl } from "./api.js";

const fmtTime = (s) => {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${sec.toString().padStart(2, "0")}`;
};

export default function App() {
  const [view, setView] = useState("landing"); // "landing" | "app"
  const [step, setStep] = useState(1);
  const [form, setForm] = useState({
    youtube_url: "",
    brand_name: "",
    brand_description: "",
    output_mode: "image",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [opportunities, setOpportunities] = useState([]);
  const [selected, setSelected] = useState({}); // id -> bool

  const [job, setJob] = useState(null);
  const pollRef = useRef(null);

  const update = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  async function onAnalyze(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await analyze(form);
      setOpportunities(res.opportunities);
      setSelected(Object.fromEntries(res.opportunities.map((o) => [o.id, true])));
      setStep(2);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function onGenerate() {
    setError("");
    const chosen = opportunities.filter((o) => selected[o.id]);
    if (chosen.length === 0) {
      setError("Select at least one moment.");
      return;
    }
    setLoading(true);
    try {
      const started = await generate({ ...form, opportunities: chosen, output_mode: form.output_mode });
      setJob(started);
      setStep(3);
      startPolling(started.job_id);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function startPolling(jobId) {
    clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const j = await getJob(jobId);
        setJob(j);
        if (j.status === "done" || j.status === "error") {
          clearInterval(pollRef.current);
        }
      } catch {
        /* keep polling */
      }
    }, 3000);
  }

  useEffect(() => () => clearInterval(pollRef.current), []);

  function reset() {
    clearInterval(pollRef.current);
    setStep(1);
    setOpportunities([]);
    setSelected({});
    setJob(null);
    setError("");
  }

  if (view === "landing") {
    return <Landing onLaunch={() => setView("app")} />;
  }

  return (
    <div className="app">
      <header className="nav">
        <button className="logo-btn" onClick={() => setView("landing")} title="Back to home">
          <Logo />
        </button>
        <span className="tagline">one video · a spectrum of brand integrations</span>
      </header>

      <Stepper step={step} />

      {error && <div className="alert">{error}</div>}

      {step === 1 && (
        <Hero
          form={form}
          update={update}
          onMode={(m) => setForm({ ...form, output_mode: m })}
          onSubmit={onAnalyze}
          loading={loading}
        />
      )}

      {step === 2 && (
        <Opportunities
          opportunities={opportunities}
          selected={selected}
          setSelected={setSelected}
          onBack={() => setStep(1)}
          onGenerate={onGenerate}
          loading={loading}
          brand={form.brand_name}
        />
      )}

      {step === 3 && <Results job={job} onReset={reset} brand={form.brand_name} />}

      <footer className="foot">Prism · built for creators</footer>
    </div>
  );
}

function Stepper({ step }) {
  const steps = ["Source", "Opportunities", "Spectrum"];
  return (
    <div className="stepper">
      {steps.map((label, i) => (
        <div key={label} className={`step-pill ${step === i + 1 ? "active" : step > i + 1 ? "done" : ""}`}>
          <span className="step-num">{i + 1}</span>
          {label}
        </div>
      ))}
    </div>
  );
}

function Hero({ form, update, onMode, onSubmit, loading }) {
  const [videoSoon, setVideoSoon] = useState(false);
  return (
    <section className="hero">
      <h1>
        One video in, a <span className="gradient-text">spectrum of brand integrations</span> out.
      </h1>
      <p className="sub">
        Paste a YouTube video and the brand you want to weave in. Prism finds the most natural
        moments, then renders before/after results you can download.
      </p>

      <form className="card form" onSubmit={onSubmit}>
        <label>
          YouTube URL
          <input
            type="text"
            placeholder="https://www.youtube.com/watch?v=…"
            value={form.youtube_url}
            onChange={update("youtube_url")}
            required
          />
        </label>
        <div className="row">
          <label>
            Brand name
            <input
              type="text"
              placeholder="e.g. Coca-Cola"
              value={form.brand_name}
              onChange={update("brand_name")}
              required
            />
          </label>
          <label>
            About the brand
            <input
              type="text"
              placeholder="e.g. classic cola in its iconic red can"
              value={form.brand_description}
              onChange={update("brand_description")}
            />
          </label>
        </div>

        <div>
          <span className="field-label">Output</span>
          <div className="mode-toggle">
            <ModeOption
              active={form.output_mode === "image"}
              onClick={() => { setVideoSoon(false); onMode("image"); }}
              title="Image"
              desc="AI-edited still frames. Fast to generate."
            />
            <ModeOption
              active={false}
              soon
              badge="Coming soon"
              onClick={() => setVideoSoon(true)}
              title="Video"
              desc="Full-motion AI-edited video clips."
            />
          </div>
          {videoSoon && (
            <p className="soon-note">🎬 Video output is coming soon — Image mode is fully live.</p>
          )}
        </div>

        <button className="btn primary" disabled={loading}>
          {loading ? "Analyzing video…" : "Find integration moments →"}
        </button>
      </form>
    </section>
  );
}

function ModeOption({ active, onClick, title, desc, soon, badge }) {
  return (
    <div className={`mode-opt ${active ? "sel" : ""} ${soon ? "soon" : ""}`} onClick={onClick} role="button">
      <div className="mode-title">
        <span className="mode-dot" /> {title}
        {badge && <span className="soon-badge">{badge}</span>}
      </div>
      <div className="mode-desc">{desc}</div>
    </div>
  );
}

function Opportunities({ opportunities, selected, setSelected, onBack, onGenerate, loading, brand }) {
  const count = Object.values(selected).filter(Boolean).length;
  return (
    <section className="panel-section">
      <div className="section-head">
        <h2 className="step-title">Where <span className="gradient-text">{brand || "the brand"}</span> fits</h2>
        <p className="sub">Pick the moments to render. Each becomes a ~10s before/after clip.</p>
      </div>
      <div className="opp-grid">
        {opportunities.map((o) => (
          <label key={o.id} className={`card opp ${selected[o.id] ? "sel" : ""}`}>
            <div className="opp-top">
              <span className="time-chip">{fmtTime(o.start_sec)}–{fmtTime(o.end_sec)}</span>
              <input
                type="checkbox"
                checked={!!selected[o.id]}
                onChange={(e) => setSelected({ ...selected, [o.id]: e.target.checked })}
              />
            </div>
            <h3>{o.product_to_insert}</h3>
            <p className="opp-scene">{o.scene_summary}</p>
            <p className="opp-idea"><b>Integration:</b> {o.integration_idea}</p>
            <p className="opp-why"><b>Why it fits:</b> {o.why_it_fits}</p>
          </label>
        ))}
      </div>
      <div className="actions">
        <button className="btn ghost" onClick={onBack}>← Back</button>
        <button className="btn primary" onClick={onGenerate} disabled={loading}>
          {loading ? "Starting…" : `Render ${count} clip${count === 1 ? "" : "s"} →`}
        </button>
      </div>
    </section>
  );
}

function Results({ job, onReset, brand }) {
  if (!job) return null;
  const pct = Math.round((job.progress || 0) * 100);
  const running = job.status === "running" || job.status === "queued";

  return (
    <section className="panel-section">
      <div className="section-head">
        <h2 className="step-title">The <span className="gradient-text">spectrum</span></h2>
        <p className="sub">{job.message || job.status}</p>
      </div>

      {running && (
        <div className="progress-wrap">
          <div className="progress"><div className="progress-bar" style={{ width: `${pct}%` }} /></div>
          <span className="progress-label">{pct}%</span>
        </div>
      )}

      {job.status === "error" && <div className="alert">{job.error}</div>}

      <div className="results-grid">
        {job.clips.map((c, i) => (
          <div key={i} className="card result">
            <div className="result-head">
              <span className="time-chip">{fmtTime(c.opportunity.start_sec)}–{fmtTime(c.opportunity.end_sec)}</span>
              <MethodBadge method={c.edit_method} failed={c.edit_failed} />
            </div>
            <h3>{c.opportunity.product_to_insert}</h3>
            <div className="ba">
              <ClipBox label="Before" url={mediaUrl(c.before_url)} kind={c.media_kind} />
              <ClipBox
                label="After"
                url={mediaUrl(c.after_url)}
                kind={c.media_kind}
                download={`${brand}-${c.media_kind === "image" ? "shot" : "clip"}-${i + 1}.${c.media_kind === "image" ? "png" : "mp4"}`}
              />
            </div>
            {c.error && <p className="tiny-note">note: {c.error}</p>}
          </div>
        ))}
      </div>

      <div className="actions">
        <button className="btn ghost" onClick={onReset}>↺ New video</button>
      </div>
    </section>
  );
}

function ClipBox({ label, url, kind, download }) {
  return (
    <div className="clipbox">
      <div className="clip-label">{label}</div>
      {url ? (
        <>
          {kind === "image" ? (
            <img src={url} alt={label} />
          ) : (
            <video src={url} controls preload="metadata" />
          )}
          {download && (
            <a className="btn tiny" href={url} download={download}>↓ Download</a>
          )}
        </>
      ) : (
        <div className="clip-placeholder"><span className="spinner" /> rendering…</div>
      )}
    </div>
  );
}

function MethodBadge({ method, failed }) {
  const map = {
    replicate: { label: "AI Video", cls: "b-ai" },
    "gemini-image": { label: "AI Edit", cls: "b-ai" },
    overlay: { label: "Overlay", cls: "b-overlay" },
    pending: { label: "Queued", cls: "b-pending" },
    none: { label: "Failed", cls: "b-fail" },
  };
  const m = map[method] || map.pending;
  return <span className={`badge ${failed ? "b-fail" : m.cls}`}>{failed ? "Fallback" : m.label}</span>;
}
