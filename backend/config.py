"""Central configuration + paths for the Prism backend."""
import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root (one level above /backend)
ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

# --- API key -----------------------------------------------------------------
# We standardize on GOOGLE_API_KEY but accept GOOGLE_CLOUD_API_KEY as a fallback
# (the user's original snippet used the latter name).
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GOOGLE_CLOUD_API_KEY")

# Replicate (video-to-video editing). Accept a couple of common env names.
REPLICATE_API_TOKEN = (
    os.environ.get("REPLICATE_API_TOKEN")
    or os.environ.get("REPLICATE_API_KEY")
    or os.environ.get("REPLICATE_TOKEN")
)
if REPLICATE_API_TOKEN:
    os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN  # the SDK reads this name

# --- Models (overridable via env) --------------------------------------------
ANALYSIS_MODEL = os.environ.get("ANALYSIS_MODEL", "gemini-3.5-flash")
EDIT_MODEL = os.environ.get("EDIT_MODEL", "gemini-omni-flash")
VEO_MODEL = os.environ.get("VEO_MODEL", "veo-3.1-generate-preview")
# Frame-level image editor — Nano Banana 2 (gemini-3.1-flash-image), confirmed reachable.
IMAGE_EDIT_MODEL = os.environ.get("IMAGE_EDIT_MODEL", "gemini-3.1-flash-image")

# Replicate video-to-video model (Kling Omni supports prompt-based editing of an
# existing clip via video_reference_type="base"). $0.15/sec at 720p "standard".
REPLICATE_VIDEO_MODEL = os.environ.get(
    "REPLICATE_VIDEO_MODEL", "kwaivgi/kling-v3-omni-video"
)
REPLICATE_MODE = os.environ.get("REPLICATE_MODE", "standard")  # standard=720p (cheap), pro=1080p
VIDEO_CLIP_SECONDS = int(os.environ.get("VIDEO_CLIP_SECONDS", "5"))  # keep short = cheap (3-10)

# Edit fallback chain toggles. omni-flash / Veo need OAuth + a real GCP project
# (they 404 / RESOURCE_PROJECT_INVALID with a bare API key), so they're OFF by
# default. Flip these to "1" once you have proper Vertex project credentials.
ENABLE_OMNI = os.environ.get("ENABLE_OMNI", "0") == "1"
ENABLE_VEO = os.environ.get("ENABLE_VEO", "0") == "1"

# --- Pipeline tuning ---------------------------------------------------------
CLIP_SECONDS = int(os.environ.get("CLIP_SECONDS", "10"))   # omni-flash output cap ~10s
MAX_DOWNLOAD_HEIGHT = int(os.environ.get("MAX_DOWNLOAD_HEIGHT", "720"))

# --- Storage -----------------------------------------------------------------
BACKEND_DIR = Path(__file__).resolve().parent
MEDIA_DIR = BACKEND_DIR / "media"          # final before/after clips (served)
TMP_DIR = BACKEND_DIR / "tmp"              # source downloads (deleted after job)
JOBS_DIR = BACKEND_DIR / "jobs"            # small JSON snapshots for recoverable review links
MEDIA_DIR.mkdir(exist_ok=True)
TMP_DIR.mkdir(exist_ok=True)
JOBS_DIR.mkdir(exist_ok=True)


def ffmpeg_exe() -> str:
    """Return a usable ffmpeg path, preferring the bundled imageio-ffmpeg binary."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"  # fall back to system ffmpeg on PATH
