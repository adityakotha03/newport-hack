"""Prism backend — FastAPI app."""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import threading

import config
import jobs as job_store
import video_pipeline
from gemini_client import analyze_video, extract_video_id
from models import AnalyzeRequest, AnalyzeResponse, GenerateRequest, Job

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
            req.youtube_url, req.brand_name, req.brand_description
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Analysis failed: {e}")

    t.join()
    src = dl.get("path")
    if src is not None:
        video_pipeline.SOURCE_CACHE[video_id] = src  # reuse in /generate
        for opp in opportunities:
            try:
                frame = video_pipeline.opportunity_frame(src, video_id, opp)
                # ffmpeg can exit 0 without writing a frame (e.g. timestamp past end),
                # so only expose the URL when a real image landed.
                if frame.exists() and frame.stat().st_size > 1024:
                    opp.frame_url = f"/media/{frame.name}"
            except Exception:  # noqa: BLE001 - frame is best-effort
                pass

    return AnalyzeResponse(video_id=video_id, opportunities=opportunities)


@app.post("/generate", response_model=Job)
def generate(req: GenerateRequest):
    if not req.opportunities:
        raise HTTPException(status_code=400, detail="No opportunities selected.")
    return job_store.start_job(req)


@app.get("/jobs/{job_id}", response_model=Job)
def get_job(job_id: str):
    job = job_store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job
