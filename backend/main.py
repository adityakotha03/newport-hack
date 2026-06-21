"""Prism backend — FastAPI app."""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import threading
from pathlib import Path

import config
import jobs as job_store
import video_pipeline
from gemini_client import analyze_video, extract_video_id
from models import (
    AnalyzeRequest,
    AnalyzeResponse,
    GenerateRequest,
    Job,
    RefineRequest,
    RefineResponse,
)

app = FastAPI(title="Prism API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/media", StaticFiles(directory=str(config.MEDIA_DIR)), name="media")


@app.get("/health")
def health():
    return {"ok": True, "has_key": bool(config.GOOGLE_API_KEY)}


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest):
    try:
        video_id = extract_video_id(req.youtube_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Fresh start: clear stale source downloads while preserving prior review assets.
    video_pipeline.clear_workspace()

    # Download the video in parallel with the Gemini analysis so preview frames are
    # ready by the time analysis returns (cached for /generate to reuse).
    dl = {}

    def _download():
        try:
            dl["path"] = video_pipeline.download_video(req.youtube_url)
        except Exception as e:  # noqa: BLE001
            dl["err"] = e

    t = threading.Thread(target=_download, daemon=True)
    t.start()

    try:
        opportunities = analyze_video(
            req.youtube_url, req.brand_name, req.brand_description, req.brand_image
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Analysis failed: {e}")

    t.join()
    src = dl.get("path")
    if src is not None:
        video_pipeline.SOURCE_CACHE[video_id] = src  # reuse in /generate
        dur = video_pipeline._clip_duration(src)
        previewable = []
        for opp in opportunities:
            # Gemini occasionally returns timestamps past the actual video length —
            # drop those so every shown opportunity has a real, editable frame.
            if opp.start_sec >= dur - 0.5:
                continue
            opp.end_sec = min(opp.end_sec, dur - 0.1)
            if opp.end_sec <= opp.start_sec:
                opp.end_sec = min(dur - 0.1, opp.start_sec + config.CLIP_SECONDS)
            try:
                frame = video_pipeline.opportunity_frame(src, video_id, opp)
                if frame.exists() and frame.stat().st_size > 1024:
                    opp.frame_url = f"/media/{frame.name}"
                    previewable.append(opp)
            except Exception:  # noqa: BLE001 - malformed timestamps are not usable opportunities
                continue
        # Keep the original response only if extraction failed for every item. The UI will show
        # a YouTube thumbnail fallback in that unlikely case.
        if previewable:
            opportunities = previewable

    return AnalyzeResponse(video_id=video_id, opportunities=opportunities)


@app.post("/generate", response_model=Job)
def generate(req: GenerateRequest):
    if not req.opportunities:
        raise HTTPException(status_code=400, detail="No opportunities selected.")
    return job_store.start_job(req)


@app.post("/refine", response_model=RefineResponse)
def refine(req: RefineRequest):
    """Refine a still-image integration using an operator-drawn placement box."""
    before_name = req.before_url.rsplit("/", 1)[-1]
    before = (config.MEDIA_DIR / before_name).resolve()
    if (
        not before_name
        or Path(before_name).name != before_name
        or before.parent != config.MEDIA_DIR.resolve()
        or not before.is_file()
    ):
        raise HTTPException(status_code=404, detail="The source image is no longer available.")
    try:
        after = video_pipeline.refine_placement(
            before,
            req.brand_name,
            req.brand_description,
            req.opportunity,
            req.placement,
            req.feedback,
            req.brand_image,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Refinement failed: {exc}")
    if req.job_id is not None and req.clip_index is not None:
        job_store.update_clip_after(req.job_id, req.clip_index, f"/media/{after.name}")
    return RefineResponse(after_url=f"/media/{after.name}")


@app.get("/jobs/{job_id}", response_model=Job)
def get_job(job_id: str):
    job = job_store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


@app.get("/reviews/{share_token}", response_model=Job)
def get_review(share_token: str):
    """Read-only job data used by a sponsor review link."""
    job = job_store.get_job_by_share_token(share_token)
    if job is None:
        raise HTTPException(status_code=404, detail="This sponsor review is unavailable.")
    return job
