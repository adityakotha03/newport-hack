import Logo from "./components/Logo.jsx";
import { ImageCompare, VideoCompare } from "./components/BeforeAfter.jsx";
import { API } from "./api.js";

const m = (f) => `${API}/media/${f}`;

export default function Landing({ onLaunch }) {
  return (
    <div className="landing">
      {/* Nav */}
      <header className="lp-nav">
        <Logo />
        <nav className="lp-links">
          <a href="#how">How it works</a>
          <a href="#results">Results</a>
          <a href="#stack">AI stack</a>
          <button className="btn primary" onClick={onLaunch}>Launch app →</button>
        </nav>
      </header>

      {/* Hero */}
      <section className="lp-hero">
        <span className="eyebrow">Reverse product placement, powered by AI</span>
        <h1>
          Turn one video into a<br />
          <span className="gradient-text">spectrum of sponsorships.</span>
        </h1>
        <p className="lp-sub">
          Prism finds the moments in a creator's existing videos where a brand fits naturally —
          then seamlessly inserts a new sponsor's product. Re-sell the back catalog. No reshoots.
        </p>
        <div className="lp-cta">
          <button className="btn primary lg" onClick={onLaunch}>Try the live demo →</button>
          <a className="btn ghost lg" href="#results">See real results</a>
        </div>

        <div className="hero-visual">
          <ImageCompare before={m("showcase_img_before.png")} after={m("showcase_img_after.png")} />
          <p className="hero-cap">Real output — a Coca-Cola can inserted into existing footage. Drag to compare.</p>
        </div>
      </section>

      {/* Problem / Impact */}
      <section className="lp-section impact">
        <div className="kpi-row">
          <div className="kpi"><b>720M+</b><span>hours of creator video uploaded yearly — most monetized once, then frozen.</span></div>
          <div className="kpi"><b>1 sponsor</b><span>per video today. The footage can't adapt to new deals.</span></div>
          <div className="kpi"><b>∞ deals</b><span>Prism unlocks — every old video becomes new ad inventory.</span></div>
        </div>
        <h2>Creators sit on a goldmine they can't re-sell.</h2>
        <p className="lp-lead">
          A video filmed with one sponsor is locked to that sponsor forever. Prism turns a static
          back catalog into living, re-sellable ad inventory — a real revenue problem with tangible value.
        </p>
      </section>

      {/* How it works */}
      <section className="lp-section" id="how">
        <span className="tag-chip">Execution · Use of AI</span>
        <h2>Three steps. AI at the core of each.</h2>
        <div className="steps">
          <Step n="1" title="Understand" model="Scene intelligence">
            Our AI watches the full video straight from its YouTube URL and pinpoints the moments
            where a product would feel native — with timestamps, scene context, and a creative idea.
          </Step>
          <Step n="2" title="Integrate" model="Generative editing">
            The brand's product is inserted seamlessly into the footage — as a crisp image edit or
            a full-motion clip. Lighting, perspective and color are matched automatically.
          </Step>
          <Step n="3" title="Deliver" model="Before / after">
            Out come downloadable before/after assets, ready to send to the new sponsor —
            the whole pipeline runs end-to-end, no manual editing.
          </Step>
        </div>
      </section>

      {/* Results */}
      <section className="lp-section" id="results">
        <span className="tag-chip">Presentation · Proof</span>
        <h2>Real generations, not mockups.</h2>
        <p className="lp-lead">Every asset below was produced by the live pipeline from a real YouTube video.</p>

        <div className="result-showcase">
          <div className="showcase-card card">
            <h3>Image output</h3>
            <ImageCompare before={m("showcase_img_before.png")} after={m("showcase_img_after.png")} />
          </div>
          <div className="showcase-card card">
            <h3>Video output</h3>
            <VideoCompare before={m("showcase_vid_before.mp4")} after={m("showcase_vid_after.mp4")} />
          </div>
        </div>
      </section>

      {/* Innovation */}
      <section className="lp-section innovation">
        <span className="tag-chip">Innovation</span>
        <h2>Not another video generator.</h2>
        <div className="why-grid">
          <Why title="Reverse product placement">
            Most AI makes video from scratch. Prism does the opposite — it reads existing footage
            and surgically inserts a brand where it belongs. A genuinely fresh angle.
          </Why>
          <Why title="A new revenue stream for creators">
            We don't compete with editing tools — we unlock inventory that didn't exist before:
            sponsorship slots inside videos that already happened.
          </Why>
          <Why title="One input, many outputs">
            The same source video can carry a different brand for every deal. White light in,
            full spectrum out — that's the Prism idea.
          </Why>
        </div>
      </section>

      {/* AI capabilities */}
      <section className="lp-section" id="stack">
        <h2 className="center">AI at the core</h2>
        <div className="stack-badges">
          <span className="stack-badge">Multimodal video understanding</span>
          <span className="stack-badge">Generative image editing</span>
          <span className="stack-badge">Video-to-video synthesis</span>
          <span className="stack-badge">End-to-end automated pipeline</span>
        </div>
      </section>

      {/* Final CTA */}
      <section className="lp-final">
        <h2>See it integrate a brand in real time.</h2>
        <button className="btn primary lg" onClick={onLaunch}>Launch Prism →</button>
      </section>

      <footer className="lp-foot">Prism · built for creators · GDG Hackathon 2026</footer>
    </div>
  );
}

function Step({ n, title, model, children }) {
  return (
    <div className="step card">
      <div className="step-n">{n}</div>
      <h3>{title}</h3>
      <span className="step-model">{model}</span>
      <p>{children}</p>
    </div>
  );
}

function Why({ title, children }) {
  return (
    <div className="why card">
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}
