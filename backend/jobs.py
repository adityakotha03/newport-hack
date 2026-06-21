"""In-memory job store + the background pipeline runner."""
import json
import re
import threading
import uuid
from pathlib import Path
from typing import Dict

import config
from gemini_client import extract_video_id
from models import ClipResult, GenerateRequest, Job
from video_pipeline import SOURCE_CACHE, download_video, produce

JOBS: Dict[str, Job] = {}
_lock = threading.Lock()


def _snapshot_path(job_id: str) -> Path | None:
    if not re.fullmatch(r"[a-f0-9]{12}", job_id):
        return None
    return config.JOBS_DIR / f"{job_id}.json"


def _job_data(job: Job) -> dict:
    return job.model_dump() if hasattr(job, "model_dump") else job.dict()


def persist_job(job: Job) -> None:
    """Atomically save lightweight job metadata so restarts do not cause 404s."""
    path = _snapshot_path(job.job_id)
    if path is None:
        return
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(_job_data(job)), encoding="utf-8")
    temp.replace(path)


def _load_snapshot(path: Path) -> Job | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return Job.model_validate(data) if hasattr(Job, "model_validate") else Job.parse_obj(data)
    except (OSError, ValueError, TypeError):
        return None


def create_job(req: GenerateRequest) -> Job:
    job = Job(
        job_id=uuid.uuid4().hex[:12],
        share_token=uuid.uuid4().hex[:16],
        youtube_url=req.youtube_url,
        brand_name=req.brand_name,
        brand_description=req.brand_description,
        status="queued",
    )
    with _lock:
        JOBS[job.job_id] = job
    persist_job(job)
    return job


def get_job(job_id: str) -> Job | None:
    with _lock:
        existing = JOBS.get(job_id)
    if existing is not None:
        return existing

    path = _snapshot_path(job_id)
    job = _load_snapshot(path) if path else None
    if job is None:
        return None
    # A background worker cannot survive a backend restart. Surface a usable error
    # instead of returning a job the browser will poll forever.
    if job.status in ("queued", "running"):
        job.status = "error"
        job.error = "The backend restarted before this render finished. Start a new render."
        job.message = "Render interrupted by backend restart."
        persist_job(job)
    with _lock:
        JOBS[job.job_id] = job
    return job


def get_job_by_share_token(share_token: str) -> Job | None:
    """Return the job exposed by a hard-to-guess, read-only review link."""
    with _lock:
        existing = next((job for job in JOBS.values() if job.share_token == share_token), None)
    if existing is not None:
        return existing
    if not re.fullmatch(r"[a-f0-9]{16}", share_token):
        return None
    for path in config.JOBS_DIR.glob("*.json"):
        job = _load_snapshot(path)
        if job is not None and job.share_token == share_token:
            return get_job(job.job_id)
    return None


def update_clip_after(job_id: str, clip_index: int, after_url: str) -> None:
    """Keep a manually refined image in the persisted sponsor review."""
    job = get_job(job_id)
    if job is None or clip_index < 0 or clip_index >= len(job.clips):
        return
    clip = job.clips[clip_index]
    clip.after_url = after_url
    clip.edit_method = "gemini-image"
    clip.edit_failed = False
    clip.error = None
    persist_job(job)


def _media_url(path: Path) -> str:
    return f"/media/{path.name}"


def run_pipeline(job_id: str, req: GenerateRequest) -> None:
    """Download once, then cut + edit each selected opportunity. Cleans up the source."""
    job = JOBS[job_id]
    job.status = "running"
    persist_job(job)
    job.message = "Downloading source video…"

    mode = req.output_mode if req.output_mode in ("image", "video") else "image"

    # Pre-seed clip results so the UI can render placeholders immediately
    job.clips = [
        ClipResult(opportunity=opp, edit_method="pending", media_kind=mode)
        for opp in req.opportunities
    ]
    persist_job(job)

    src: Path | None = None
    try:
        # Reuse the copy /analyze already downloaded, if available.
        try:
            vid = extract_video_id(req.youtube_url)
        except Exception:  # noqa: BLE001
            vid = None
        cached = SOURCE_CACHE.pop(vid, None) if vid else None
        if cached is not None and cached.exists():
            src = cached
        else:
            src = download_video(req.youtube_url)
        total = len(req.opportunities)

        for i, opp in enumerate(req.opportunities):
            job.message = f"Processing opportunity {i + 1} of {total}…"
            result = job.clips[i]
            try:
                before_path, after_path, kind, method, err = produce(
                    src, opp, req.brand_name, req.brand_description, job_id, mode,
                    req.brand_image,
                )
                result.media_kind = kind
                result.edit_method = method
                result.before_url = _media_url(before_path) if before_path else None
                if after_path is not None:
                    result.after_url = _media_url(after_path)
                else:
                    result.edit_failed = True
                    result.after_url = result.before_url  # show something
                result.error = err
            except Exception as e:  # noqa: BLE001 - per-clip failures shouldn't kill the job
                result.edit_failed = True
                result.error = str(e)

            job.progress = (i + 1) / total
            persist_job(job)

        job.status = "done"
        job.message = "All clips ready."
    except Exception as e:  # noqa: BLE001
        job.status = "error"
        job.error = str(e)
        job.message = "Pipeline failed."
    finally:
        persist_job(job)
        # Storage hygiene: delete the heavy source download, keep only final clips.
        if src is not None:
            try:
                src.unlink(missing_ok=True)
            except Exception:
                pass


def start_job(req: GenerateRequest) -> Job:
    job = create_job(req)
    t = threading.Thread(target=run_pipeline, args=(job.job_id, req), daemon=True)
    t.start()
    return job
