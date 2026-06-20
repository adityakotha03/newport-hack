"""In-memory job store + the background pipeline runner."""
import threading
import uuid
from pathlib import Path
from typing import Dict

import config
from models import ClipResult, GenerateRequest, Job
from video_pipeline import download_video, produce

JOBS: Dict[str, Job] = {}
_lock = threading.Lock()


def create_job() -> Job:
    job = Job(job_id=uuid.uuid4().hex[:12], status="queued")
    with _lock:
        JOBS[job.job_id] = job
    return job


def get_job(job_id: str) -> Job | None:
    return JOBS.get(job_id)


def _media_url(path: Path) -> str:
    return f"/media/{path.name}"


def run_pipeline(job_id: str, req: GenerateRequest) -> None:
    """Download once, then cut + edit each selected opportunity. Cleans up the source."""
    job = JOBS[job_id]
    job.status = "running"
    job.message = "Downloading source video…"

    mode = req.output_mode if req.output_mode in ("image", "video") else "image"

    # Pre-seed clip results so the UI can render placeholders immediately
    job.clips = [
        ClipResult(opportunity=opp, edit_method="pending", media_kind=mode)
        for opp in req.opportunities
    ]

    src: Path | None = None
    try:
        src = download_video(req.youtube_url)
        total = len(req.opportunities)

        for i, opp in enumerate(req.opportunities):
            job.message = f"Processing opportunity {i + 1} of {total}…"
            result = job.clips[i]
            try:
                before_path, after_path, kind, method, err = produce(
                    src, opp, req.brand_name, req.brand_description, job_id, mode
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

        job.status = "done"
        job.message = "All clips ready."
    except Exception as e:  # noqa: BLE001
        job.status = "error"
        job.error = str(e)
        job.message = "Pipeline failed."
    finally:
        # Storage hygiene: delete the heavy source download, keep only final clips.
        if src is not None:
            try:
                src.unlink(missing_ok=True)
            except Exception:
                pass


def start_job(req: GenerateRequest) -> Job:
    job = create_job()
    t = threading.Thread(target=run_pipeline, args=(job.job_id, req), daemon=True)
    t.start()
    return job
