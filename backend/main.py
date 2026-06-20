"""Prism backend — FastAPI app."""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import config
import jobs as job_store
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
    try:
        opportunities = analyze_video(
            req.youtube_url, req.brand_name, req.brand_description
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Analysis failed: {e}")
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
