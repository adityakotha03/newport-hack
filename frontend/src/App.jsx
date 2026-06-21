import { useEffect, useRef, useState } from "react";
import Logo from "./components/Logo.jsx";
import Landing from "./Landing.jsx";
import { ImageCompare } from "./components/BeforeAfter.jsx";
import { analyze, generate, getJob, getReview, mediaUrl, refinePlacement } from "./api.js";

const fmtTime = (s) => {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${sec.toString().padStart(2, "0")}`;
};

const STUDIO_PATH = "/studio";
const REVIEW_PATH = "/review/";

function viewForPath(path) {
  if (path.startsWith(REVIEW_PATH)) return "review";
  return path === STUDIO_PATH ? "app" : "landing";
}

function reviewTokenFromPath(path) {
  return path.startsWith(REVIEW_PATH) ? path.slice(REVIEW_PATH.length).split("/")[0] : "";
}

export default function App() {
  const [view, setView] = useState(() =>
    viewForPath(window.location.pathname)
  );
  const [step, setStep] = useState(1);
  const [form, setForm] = useState({
    youtube_url: "",
    brand_name: "",
    brand_description: "",
    brand_image: null,
    output_mode: "image",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [opportunities, setOpportunities] = useState([]);
  const [videoId, setVideoId] = useState("");
  const [selected, setSelected] = useState({}); // id -> bool

  const [job, setJob] = useState(null);
  const pollRef = useRef(null);

  const update = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  function navigate(path) {
    window.history.pushState({}, "", path);
    setView(viewForPath(path));
  }

  async function onAnalyze(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await analyze(form);
      setOpportunities(res.opportunities);
      setVideoId(res.video_id || "");
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
      } catch (err) {
        clearInterval(pollRef.current);
        setError(`Could not retrieve this render: ${err.message || "backend unavailable"}`);
        setJob((current) => current ? {
          ...current,
          status: "error",
          error: "The render status is no longer available.",
        } : current);
      }
    }, 3000);
  }

  useEffect(() => () => clearInterval(pollRef.current), []);
  useEffect(() => {
    const onPopState = () => setView(viewForPath(window.location.pathname));
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  function reset() {
    clearInterval(pollRef.current);
    setStep(1);
    setOpportunities([]);
    setSelected({});
    setJob(null);
    setError("");
  }

  if (view === "landing") {
    return <Landing onLaunch={() => navigate(STUDIO_PATH)} />;
  }

  if (view === "review") {
    return <SponsorReview
      shareToken={reviewTokenFromPath(window.location.pathname)}
      onHome={() => navigate("/")}
    />;
  }

  return (
    <div className="app">
      <header className="nav">
        <button className="logo-btn" onClick={() => navigate("/")} title="Back to home">
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
          onBrandImage={(v) => setForm((f) => ({ ...f, brand_image: v }))}
          onSubmit={onAnalyze}
          loading={loading}
        />
      )}

      {step === 2 && (
        <Opportunities
          opportunities={opportunities}
          videoId={videoId}
          selected={selected}
          setSelected={setSelected}
          onBack={() => setStep(1)}
          onGenerate={onGenerate}
          loading={loading}
          brand={form.brand_name}
        />
      )}

      {step === 3 && (
        <Results
          job={job}
          onReset={reset}
          brand={form.brand_name}
          brandDescription={form.brand_description}
          brandImage={form.brand_image}
          onRefined={(index, afterUrl) => {
            setJob((current) => {
              if (!current) return current;
              return {
                ...current,
                clips: current.clips.map((clip, clipIndex) => (
                  clipIndex === index
                    ? { ...clip, after_url: afterUrl, edit_method: "gemini-image", edit_failed: false, error: null }
                    : clip
                )),
              };
            });
          }}
        />
      )}

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

function Hero({ form, update, onMode, onBrandImage, onSubmit, loading }) {
  const [videoSoon, setVideoSoon] = useState(false);

  function onFile(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => onBrandImage(reader.result); // data: URL
    reader.readAsDataURL(file);
  }

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
          <span className="field-label">Brand reference image <span className="opt">(optional — improves accuracy)</span></span>
          {form.brand_image ? (
            <div className="ref-preview">
              <img src={form.brand_image} alt="brand reference" />
              <div className="ref-actions">
                <span>Reference added</span>
                <button type="button" className="btn tiny" onClick={() => onBrandImage(null)}>Remove</button>
              </div>
            </div>
          ) : (
            <label className="ref-drop">
              <input type="file" accept="image/*" onChange={onFile} hidden />
              <span>＋ Upload a product / logo image</span>
            </label>
          )}
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

function Opportunities({ opportunities, videoId, selected, setSelected, onBack, onGenerate, loading, brand }) {
  const count = Object.values(selected).filter(Boolean).length;
  return (
    <section className="panel-section">
      <div className="section-head">
        <h2 className="step-title">Where <span className="gradient-text">{brand || "the brand"}</span> fits</h2>
        <p className="sub">Preview each moment, then pick the ones to render.</p>
      </div>
      <div className="opp-grid">
        {opportunities.map((o) => (
          <div key={o.id} className={`card opp ${selected[o.id] ? "sel" : ""}`}>
            <div className="opp-preview">
              <PreviewFrame
                src={mediaUrl(o.frame_url)}
                videoId={videoId}
                alt={o.scene_summary}
              />
            </div>
            <label className="opp-body">
              <div className="opp-top">
                <ConfidenceBadge score={o.placement_confidence} />
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
          </div>
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

function PreviewFrame({ src, videoId, alt }) {
  const [useFallback, setUseFallback] = useState(!src);
  const fallback = videoId ? `https://i.ytimg.com/vi/${videoId}/hqdefault.jpg` : null;
  const imageSrc = useFallback ? fallback : src;

  if (!imageSrc) {
    return <div className="clip-placeholder">preview unavailable</div>;
  }
  return (
    <img
      src={imageSrc}
      alt={alt || "Video preview"}
      loading="lazy"
      onError={() => setUseFallback(true)}
    />
  );
}

function Results({ job, onReset, brand, brandDescription, brandImage, onRefined }) {
  const [editingIndex, setEditingIndex] = useState(null);
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

      <div className="results-list">
        {job.clips.map((c, i) => {
          const before = mediaUrl(c.before_url);
          const after = mediaUrl(c.after_url);
          const ready = !!after;
          const dl = `${brand}-${c.media_kind === "image" ? "shot" : "clip"}-${i + 1}.${c.media_kind === "image" ? "png" : "mp4"}`;
          return (
            <div key={i} className="card result-big">
              <div className="result-head">
                <span className="time-chip">{fmtTime(c.opportunity.start_sec)}–{fmtTime(c.opportunity.end_sec)}</span>
                <h3>{c.opportunity.product_to_insert}</h3>
                <ConfidenceBadge score={c.opportunity.placement_confidence} />
                <MethodBadge method={c.edit_method} failed={c.edit_failed} />
              </div>

              {!ready ? (
                <div className="clip-placeholder big"><span className="spinner" /> rendering…</div>
              ) : c.media_kind === "image" ? (
                <ImageCompare before={before} after={after} />
              ) : (
                <div className="ba">
                  <ClipBox label="Before" url={before} kind={c.media_kind} />
                  <ClipBox label="After" url={after} kind={c.media_kind} download={dl} />
                </div>
              )}

              {ready && (
                <div className="result-actions">
                  {c.media_kind === "image" && c.before_url && (
                    <button className="btn tiny" type="button" onClick={() => setEditingIndex(i)}>
                      Refine placement
                    </button>
                  )}
                  <a className="btn tiny" href={after} download={dl}>↓ Download {c.media_kind === "image" ? "image" : "clip"}</a>
                  {c.error && <span className="tiny-note">note: {c.error}</span>}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="actions">
        <button className="btn ghost" onClick={onReset}>↺ New video</button>
        {job.status === "done" && job.share_token && <SponsorReviewLink shareToken={job.share_token} />}
      </div>
      {editingIndex !== null && job.clips[editingIndex] && (
        <PlacementEditor
          clip={job.clips[editingIndex]}
          jobId={job.job_id}
          clipIndex={editingIndex}
          brand={brand}
          brandDescription={brandDescription}
          brandImage={brandImage}
          onClose={() => setEditingIndex(null)}
          onSaved={(afterUrl) => {
            onRefined(editingIndex, afterUrl);
            setEditingIndex(null);
          }}
        />
      )}
    </section>
  );
}

function PlacementEditor({ clip, jobId, clipIndex, brand, brandDescription, brandImage, onClose, onSaved }) {
  const stageRef = useRef(null);
  const dragStartRef = useRef(null);
  const [box, setBox] = useState(null);
  const [draft, setDraft] = useState(null);
  const [feedback, setFeedback] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const activeBox = draft || box;

  useEffect(() => {
    const onKeyDown = (event) => {
      if (event.key === "Escape" && !saving) onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose, saving]);

  function pointFor(event) {
    const rect = stageRef.current?.getBoundingClientRect();
    if (!rect) return null;
    return {
      x: Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width)),
      y: Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height)),
    };
  }

  function boxFrom(start, end) {
    const x = Math.min(start.x, end.x);
    const y = Math.min(start.y, end.y);
    return { x, y, width: Math.abs(end.x - start.x), height: Math.abs(end.y - start.y) };
  }

  function startDraw(event) {
    if (saving) return;
    const point = pointFor(event);
    if (!point) return;
    dragStartRef.current = point;
    setBox(null);
    setDraft({ x: point.x, y: point.y, width: 0, height: 0 });
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function draw(event) {
    if (!dragStartRef.current) return;
    const point = pointFor(event);
    if (point) setDraft(boxFrom(dragStartRef.current, point));
  }

  function finishDraw(event) {
    const start = dragStartRef.current;
    const point = pointFor(event);
    dragStartRef.current = null;
    if (!start || !point) return;
    const nextBox = boxFrom(start, point);
    setDraft(null);
    if (nextBox.width < 0.02 || nextBox.height < 0.02) {
      setError("Draw a larger target area.");
      return;
    }
    setError("");
    setBox(nextBox);
  }

  async function submit() {
    if (!box) {
      setError("Draw the area where the product should appear.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const result = await refinePlacement({
        before_url: clip.before_url,
        brand_name: brand,
        brand_description: brandDescription,
        brand_image: brandImage,
        opportunity: clip.opportunity,
        placement: box,
        feedback,
        job_id: jobId,
        clip_index: clipIndex,
      });
      onSaved(result.after_url);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <div className="placement-modal" role="dialog" aria-modal="true" aria-labelledby="placement-title">
        <div className="modal-head">
          <div>
            <h3 id="placement-title">Refine placement</h3>
            <p>Draw the exact area where {clip.opportunity.product_to_insert} should appear.</p>
          </div>
          <button className="icon-btn" type="button" onClick={onClose} disabled={saving} aria-label="Close editor">x</button>
        </div>

        <div
          className="placement-stage"
          ref={stageRef}
          onPointerDown={startDraw}
          onPointerMove={draw}
          onPointerUp={finishDraw}
          onPointerCancel={() => {
            dragStartRef.current = null;
            setDraft(null);
          }}
        >
          <img src={mediaUrl(clip.before_url)} alt="Source frame for placement refinement" draggable="false" />
          {activeBox && (
            <div
              className="placement-box"
              style={{
                left: `${activeBox.x * 100}%`,
                top: `${activeBox.y * 100}%`,
                width: `${activeBox.width * 100}%`,
                height: `${activeBox.height * 100}%`,
              }}
            />
          )}
        </div>

        <label className="placement-feedback">
          Correction for the model (optional)
          <textarea
            value={feedback}
            onChange={(event) => setFeedback(event.target.value)}
            placeholder="e.g. Place it on the empty side table, not in the person's hand."
            maxLength={1000}
          />
        </label>
        {error && <div className="alert modal-alert">{error}</div>}
        <div className="modal-actions">
          <button className="btn ghost" type="button" onClick={() => { setBox(null); setDraft(null); setError(""); }} disabled={saving}>
            Clear selection
          </button>
          <span />
          <button className="btn ghost" type="button" onClick={onClose} disabled={saving}>Cancel</button>
          <button className="btn primary" type="button" onClick={submit} disabled={saving}>
            {saving ? "Refining..." : "Generate refinement"}
          </button>
        </div>
      </div>
    </div>
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

function confidenceScore(score) {
  const parsed = Number(score);
  return Number.isFinite(parsed) ? Math.max(0, Math.min(100, Math.round(parsed))) : 75;
}

function ConfidenceBadge({ score }) {
  const value = confidenceScore(score);
  const tone = value >= 85 ? "strong" : value >= 70 ? "good" : "review";
  return <span className={`confidence ${tone}`}>{value}% fit</span>;
}

function SponsorReviewLink({ shareToken }) {
  const [copied, setCopied] = useState(false);
  const url = `${window.location.origin}${REVIEW_PATH}${shareToken}`;

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      window.prompt("Copy this sponsor review link:", url);
    }
  }

  return (
    <div className="review-link-actions">
      <a className="btn ghost" href={`${REVIEW_PATH}${shareToken}`} target="_blank" rel="noreferrer">
        Open sponsor review
      </a>
      <button className="btn primary" type="button" onClick={copyLink}>
        {copied ? "Link copied" : "Copy sponsor review link"}
      </button>
    </div>
  );
}

function SponsorReview({ shareToken, onHome }) {
  const [job, setJob] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let current = true;
    getReview(shareToken)
      .then((review) => current && setJob(review))
      .catch((err) => current && setError(err.message));
    return () => { current = false; };
  }, [shareToken]);

  if (error) {
    return (
      <main className="review-page review-state">
        <button className="btn ghost" type="button" onClick={onHome}>Back to Prism</button>
        <div className="alert">{error}</div>
      </main>
    );
  }

  if (!job) {
    return <main className="review-page review-state"><span className="spinner" /> Loading sponsor review...</main>;
  }

  const clips = job.clips || [];
  const ready = clips.filter((clip) => clip.after_url);
  const averageConfidence = clips.length
    ? Math.round(clips.reduce((sum, clip) => sum + confidenceScore(clip.opportunity.placement_confidence), 0) / clips.length)
    : 0;

  return (
    <main className="review-page">
      <header className="review-nav">
        <button className="logo-btn" type="button" onClick={onHome} title="Prism home"><Logo /></button>
        <button className="btn ghost print-control" type="button" onClick={() => window.print()}>Print / Save PDF</button>
      </header>

      <section className="sponsor-sheet">
        <div className="sponsor-intro">
          <p className="eyebrow">Sponsor integration review</p>
          <h1>{job.brand_name || "Brand"} x existing creator video</h1>
          <p>{job.brand_description || "Native integration concepts selected from the source video."}</p>
          <a href={job.youtube_url} target="_blank" rel="noreferrer">View source video</a>
        </div>

        <div className="review-metrics" aria-label="Review metrics">
          <div><strong>{clips.length}</strong><span>placements selected</span></div>
          <div><strong>{ready.length}</strong><span>previews rendered</span></div>
          <div><strong>{averageConfidence}%</strong><span>average placement fit</span></div>
        </div>

        <section className="review-moments" aria-label="Proposed placements">
          {clips.map((clip, index) => {
            const asset = mediaUrl(clip.after_url);
            return (
              <article className="review-moment" key={`${clip.opportunity.id}-${index}`}>
                <div className="review-copy">
                  <div className="review-moment-head">
                    <span className="time-chip">{fmtTime(clip.opportunity.start_sec)} - {fmtTime(clip.opportunity.end_sec)}</span>
                    <ConfidenceBadge score={clip.opportunity.placement_confidence} />
                  </div>
                  <h2>{clip.opportunity.product_to_insert}</h2>
                  <p>{clip.opportunity.integration_idea}</p>
                  <p className="review-why">{clip.opportunity.why_it_fits}</p>
                </div>
                {asset && (clip.media_kind === "image" ? (
                  <img className="review-asset" src={asset} alt={`${job.brand_name} integration preview`} />
                ) : (
                  <video className="review-asset" src={asset} controls preload="metadata" />
                ))}
              </article>
            );
          })}
        </section>
      </section>
    </main>
  );
}
