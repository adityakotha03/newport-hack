"""Download, cut, and brand-edit clips.

Two output modes:
  - IMAGE: extract a keyframe, insert the product with gemini-2.5-flash-image (cheap, fast).
  - VIDEO: cut a short clip, edit it with a Replicate video-to-video model (Kling Omni),
           with graceful fallback to the image-edit-rendered-to-clip, then a badge overlay.
"""
import subprocess
import uuid
from pathlib import Path
from typing import Optional, Tuple

from google.genai import types

import config
from gemini_client import decode_image, get_client, _SAFETY
from models import Opportunity, PlacementBox

Result = Tuple[Optional[Path], Optional[Path], str, str, Optional[str]]
# (before_path, after_path, media_kind, method, error)

# Cache of already-downloaded source videos, keyed by youtube video id, so /generate
# can reuse the copy /analyze downloaded (instead of downloading twice).
SOURCE_CACHE: dict = {}


def clear_workspace() -> None:
    """Delete temporary source files and reset the source cache.

    Completed media stays available so existing job and sponsor-review links do not
    break when someone begins a new analysis.
    """
    for f in config.TMP_DIR.glob("*"):
        try:
            if f.is_file():
                f.unlink()
        except Exception:  # noqa: BLE001
            pass
    SOURCE_CACHE.clear()


# ---------------------------------------------------------------------------
# Download + cut (yt-dlp / ffmpeg)
# ---------------------------------------------------------------------------
def download_video(youtube_url: str) -> Path:
    """Download a (resolution-capped) copy of the video into TMP_DIR. Returns the path."""
    import yt_dlp

    out_tmpl = str(config.TMP_DIR / f"src_{uuid.uuid4().hex[:8]}.%(ext)s")
    ydl_opts = {
        "format": f"bestvideo[height<={config.MAX_DOWNLOAD_HEIGHT}]+bestaudio/best[height<={config.MAX_DOWNLOAD_HEIGHT}]/best",
        "outtmpl": out_tmpl,
        "merge_output_format": "mp4",
        "ffmpeg_location": config.ffmpeg_exe(),
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(youtube_url, download=True)
        path = Path(ydl.prepare_filename(info))
    if not path.exists():
        mp4 = path.with_suffix(".mp4")
        if mp4.exists():
            path = mp4
    if not path.exists():
        raise RuntimeError("Download finished but output file was not found.")
    return path


def cut_clip(src: Path, start: float, end: float, out_name: str) -> Path:
    """Cut [start, end] from src into MEDIA_DIR/out_name (re-encoded for a clean cut)."""
    duration = max(0.5, end - start)
    out_path = config.MEDIA_DIR / out_name
    cmd = [
        config.ffmpeg_exe(), "-y",
        "-ss", str(start),
        "-i", str(src),
        "-t", str(duration),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        str(out_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return out_path


def _extract_frame(src: Path, out_png: Path, at: float = 1.0) -> None:
    """Grab a single representative frame at `at` seconds."""
    out_png.unlink(missing_ok=True)
    cmd = [
        config.ffmpeg_exe(), "-y",
        "-i", str(src), "-ss", str(max(0, at)),
        "-an", "-frames:v", "1", "-update", "1",
        str(out_png),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    if not out_png.exists() or out_png.stat().st_size <= 1024:
        raise RuntimeError("ffmpeg did not produce a usable preview frame")


def opportunity_frame(src: Path, video_id: str, opp: Opportunity) -> Path:
    """Save a preview frame, retrying nearby timestamps when a seek lands between frames."""
    out = config.MEDIA_DIR / f"oppframe_{video_id}_{opp.id}.png"
    duration = _clip_duration(src)
    latest = max(0, duration - 0.1)
    times = (
        (opp.start_sec + opp.end_sec) / 2,
        opp.start_sec + 0.25,
        opp.end_sec - 0.25,
        0,
    )
    last_error = None
    for at in dict.fromkeys(round(min(latest, max(0, value)), 3) for value in times):
        try:
            _extract_frame(src, out, at=at)
            return out
        except Exception as exc:  # noqa: BLE001 - the next timestamp may be decodable
            last_error = exc
    raise RuntimeError(f"Could not extract preview frame: {last_error}")


def _clip_duration(path: Path) -> float:
    try:
        res = subprocess.run(
            [config.ffmpeg_exe(), "-i", str(path)], capture_output=True, text=True
        )
        import re
        m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", res.stderr)
        if m:
            h, mm, ss = m.groups()
            return int(h) * 3600 + int(mm) * 60 + float(ss)
    except Exception:
        pass
    return float(config.VIDEO_CLIP_SECONDS)


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------
def _image_prompt(brand_name: str, brand_desc: str, opp: Opportunity) -> str:
    return (
        "You are a world-class professional photo retoucher and VFX compositor specializing in "
        "photorealistic, invisible product placement for high-end advertising. Edit this photograph "
        f"to place the product '{opp.product_to_insert}' from the brand '{brand_name}' into the scene "
        "so naturally that a viewer cannot tell it was added. "
        f"Suggested placement: {opp.integration_idea}. Brand context: {brand_desc}. "
        "PLACEMENT must be physically believable: put the product on a real supporting surface where "
        "an object would actually rest (not floating, not awkwardly centered), at a realistic size "
        "relative to nearby objects and people, at a natural distance and angle. "
        "INTEGRATION must be flawless: correct perspective and orientation, accurate grounding with "
        "contact shadows, matching light direction and color temperature, proper occlusion behind "
        "foreground elements, matching depth of field/blur, grain and color grade of the photo. "
        "The result must look like it was physically present when the photo was taken — never like a "
        "sticker or cut-and-paste. Do NOT alter anything else: keep people, poses, background, "
        "framing and style identical. Output only the final edited photograph."
    )


def _video_prompt(brand_name: str, brand_desc: str, opp: Opportunity) -> str:
    return (
        "You are a world-class VFX compositor doing photorealistic product placement. Seamlessly "
        f"integrate the product '{opp.product_to_insert}' from the brand '{brand_name}' into this "
        f"video. Placement: {opp.integration_idea}. Brand context: {brand_desc}. The product must be "
        "realistically scaled and branded, with perspective, motion, lighting, shadows and color "
        "grading that match the footage so it looks like it was filmed there. Keep the original "
        "scene, people and actions completely unchanged."
    )


def _make_placement_guide(frame: Path, placement: PlacementBox) -> Path:
    """Create an annotated copy used as a visual target for the image-edit model."""
    from PIL import Image, ImageDraw

    guide_path = config.TMP_DIR / f"placement_{uuid.uuid4().hex[:8]}.png"
    with Image.open(frame) as source:
        image = source.convert("RGB")
    width, height = image.size
    left = min(width - 1, max(0, round(placement.x * width)))
    top = min(height - 1, max(0, round(placement.y * height)))
    right = min(width - 1, max(left + 1, round((placement.x + placement.width) * width)))
    bottom = min(height - 1, max(top + 1, round((placement.y + placement.height) * height)))
    stroke = max(3, min(width, height) // 180)

    ImageDraw.Draw(image).rectangle(
        (left, top, right, bottom), outline=(245, 68, 68), width=stroke
    )
    image.save(guide_path)
    return guide_path


# ---------------------------------------------------------------------------
# Gemini image edit (the IMAGE mode + a VIDEO fallback)
# ---------------------------------------------------------------------------
def _gemini_edit_image(frame: Path, brand_name: str, brand_desc: str,
                       opp: Opportunity, out_png: Path,
                       brand_image: Optional[str] = None,
                       placement: Optional[PlacementBox] = None,
                       feedback: str = "") -> bool:
    """Insert the product into a still frame with Nano Banana 2 (gemini-3.1-flash-image)."""
    client = get_client()
    prompt = _image_prompt(brand_name, brand_desc, opp)
    parts = [types.Part.from_bytes(data=frame.read_bytes(), mime_type="image/png")]
    guide = None
    if placement is not None:
        guide = _make_placement_guide(frame, placement)
        parts.append(types.Part.from_bytes(data=guide.read_bytes(), mime_type="image/png"))
        prompt += (
            " A placement guide is attached as the second image. Its red rectangle marks the "
            "exact target region. Place the entire product inside that region, preserve its "
            "boundaries and perspective, and never include the red rectangle in the output."
        )
    ref = decode_image(brand_image)
    if ref is not None:
        parts.append(types.Part.from_bytes(data=ref[0], mime_type=ref[1]))
        prompt += (
            f" A product reference is attached as the {'third' if placement is not None else 'second'} "
            "image. Match its exact appearance, logo, colors and proportions precisely."
        )
    if feedback.strip():
        prompt += f" Additional operator instruction: {feedback.strip()[:1000]}"
    parts.append(types.Part(text=prompt))
    contents = [types.Content(role="user", parts=parts)]
    resp = client.models.generate_content(
        model=config.IMAGE_EDIT_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"], safety_settings=_SAFETY
        ),
    )
    for cand in (resp.candidates or []):
        for part in (cand.content.parts if cand.content else []):
            data = getattr(getattr(part, "inline_data", None), "data", None)
            if data:
                out_png.write_bytes(data)
                if guide is not None:
                    guide.unlink(missing_ok=True)
                return True
    if guide is not None:
        guide.unlink(missing_ok=True)
    return False


def refine_placement(before_png: Path, brand_name: str, brand_desc: str,
                     opp: Opportunity, placement: PlacementBox, feedback: str = "",
                     brand_image: Optional[str] = None) -> Path:
    """Regenerate an image edit with a user-defined visual placement constraint."""
    out_png = config.MEDIA_DIR / f"refined_{opp.id}_{uuid.uuid4().hex[:8]}.png"
    if not _gemini_edit_image(
        before_png, brand_name, brand_desc, opp, out_png, brand_image, placement, feedback
    ):
        raise RuntimeError("The image model returned no refined image.")
    return out_png


def _render_clip_from_image(image_png: Path, audio_src: Path, out_path: Path) -> None:
    """Render a still image into a clip with a gentle zoom, reusing the source audio."""
    dur = _clip_duration(audio_src)
    frames = max(25, int(dur * 25))
    vf = (
        "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,"
        f"zoompan=z='min(zoom+0.0006,1.12)':d={frames}:s=1280x720:fps=25,format=yuv420p"
    )
    cmd = [
        config.ffmpeg_exe(), "-y",
        "-loop", "1", "-i", str(image_png),
        "-i", str(audio_src),
        "-filter_complex", f"[0:v]{vf}[v]",
        "-map", "[v]", "-map", "1:a?",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-t", str(dur), "-shortest", "-movflags", "+faststart",
        str(out_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)


# ---------------------------------------------------------------------------
# Replicate video-to-video (Kling Omni) — the VIDEO mode primary
# ---------------------------------------------------------------------------
def _replicate_bytes(output) -> Optional[bytes]:
    """Normalize a Replicate output (FileOutput / URL / list) into raw bytes."""
    import requests

    if isinstance(output, list):
        output = output[0] if output else None
    if output is None:
        return None
    if hasattr(output, "read"):           # FileOutput
        try:
            return output.read()
        except Exception:
            pass
    url = getattr(output, "url", None) or (output if isinstance(output, str) else None)
    if url:
        r = requests.get(url, timeout=600)
        r.raise_for_status()
        return r.content
    return None


def _upload_public(path: Path) -> str:
    """Upload a file to a public temp host and return a direct, extension-bearing URL."""
    import requests

    r = requests.post(
        "https://tmpfiles.org/api/v1/upload",
        files={"file": open(path, "rb")},
        timeout=180,
    )
    r.raise_for_status()
    url = r.json()["data"]["url"]
    # convert the viewer URL to the direct-download URL (keeps the .mp4 suffix)
    return url.replace("tmpfiles.org/", "tmpfiles.org/dl/")


def _try_replicate_v2v(before: Path, brand_name: str, brand_desc: str,
                       opp: Opportunity, out_path: Path) -> bool:
    """Edit the clip with a Replicate video-to-video model. Returns True on success."""
    import replicate

    if not config.REPLICATE_API_TOKEN:
        raise RuntimeError("REPLICATE_API_TOKEN is not set in .env")

    prompt = _video_prompt(brand_name, brand_desc, opp)
    duration = min(10, max(3, round(_clip_duration(before))))
    # Kling needs a PUBLIC, direct .mp4 URL. Replicate's own file URLs are auth'd and
    # redirect to extension-less signed URLs (model rejects them: "must be .mp4 .. Got .").
    # So host the clip on a public temp host and pass that direct link.
    ref_url = _upload_public(before)
    output = replicate.run(
        config.REPLICATE_VIDEO_MODEL,
        input={
            "prompt": prompt,
            "reference_video": ref_url,
            "video_reference_type": "base",   # = video editing
            "mode": config.REPLICATE_MODE,     # standard (720p) keeps cost low
            "duration": duration,
            "aspect_ratio": "16:9",
            "keep_original_sound": True,
        },
    )
    data = _replicate_bytes(output)
    if data:
        out_path.write_bytes(data)
        return True
    return False


# ---------------------------------------------------------------------------
# Overlay safety net (deterministic)
# ---------------------------------------------------------------------------
def _make_badge_png(brand_name: str, product: str, png_path: Path,
                    width: int = 560, height: int = 150) -> None:
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([0, 0, width - 1, height - 1], radius=24,
                           fill=(14, 14, 18, 210), outline=(124, 108, 255, 255), width=3)

    def _font(size: int):
        for name in ("seguisb.ttf", "segoeui.ttf", "arial.ttf"):
            try:
                return ImageFont.truetype(name, size)
            except Exception:
                continue
        return ImageFont.load_default()

    draw.text((28, 26), brand_name[:28], font=_font(46), fill=(255, 255, 255, 255))
    draw.text((28, 88), f"feat. {product}"[:46], font=_font(26), fill=(150, 170, 255, 255))
    img.save(png_path)


def _overlay_badge_video(before: Path, brand_name: str, product: str, out_path: Path) -> bool:
    badge = config.TMP_DIR / f"badge_{uuid.uuid4().hex[:6]}.png"
    try:
        _make_badge_png(brand_name, product, badge)
        cmd = [
            config.ffmpeg_exe(), "-y",
            "-i", str(before), "-i", str(badge),
            "-filter_complex", "[0:v][1:v]overlay=W-w-40:H-h-40:format=auto",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-c:a", "copy", "-movflags", "+faststart",
            str(out_path),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    finally:
        badge.unlink(missing_ok=True)


def _overlay_badge_image(before_png: Path, brand_name: str, product: str, out_png: Path) -> bool:
    from PIL import Image
    badge = config.TMP_DIR / f"badge_{uuid.uuid4().hex[:6]}.png"
    try:
        _make_badge_png(brand_name, product, badge)
        base = Image.open(before_png).convert("RGBA")
        ov = Image.open(badge).convert("RGBA")
        base.alpha_composite(ov, (base.width - ov.width - 30, base.height - ov.height - 30))
        base.convert("RGB").save(out_png)
        return True
    finally:
        badge.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Orchestration per opportunity
# ---------------------------------------------------------------------------
def produce_image(src: Path, opp: Opportunity, brand_name: str, brand_desc: str,
                  job_id: str, brand_image: Optional[str] = None) -> Result:
    """IMAGE mode: keyframe before + AI-edited after (PNG)."""
    before_png = config.MEDIA_DIR / f"before_{opp.id}_{job_id}.png"
    after_png = config.MEDIA_DIR / f"after_{opp.id}_{uuid.uuid4().hex[:6]}.png"
    mid = (opp.start_sec + opp.end_sec) / 2
    _extract_frame(src, before_png, at=mid)

    try:
        if _gemini_edit_image(before_png, brand_name, brand_desc, opp, after_png, brand_image):
            return before_png, after_png, "image", "gemini-image", None
    except Exception as e:  # noqa: BLE001
        err = str(e)
    else:
        err = "model returned no image"

    # fallback: badge overlay on the frame
    try:
        if _overlay_badge_image(before_png, brand_name, opp.product_to_insert, after_png):
            return before_png, after_png, "image", "overlay", err
    except Exception as e:  # noqa: BLE001
        err = f"{err}; overlay: {e}"
    return before_png, None, "image", "none", err


def produce_video(src: Path, opp: Opportunity, brand_name: str, brand_desc: str,
                  job_id: str, brand_image: Optional[str] = None) -> Result:
    """VIDEO mode: short before clip + Replicate-edited after clip (with fallbacks)."""
    end = opp.start_sec + min(config.VIDEO_CLIP_SECONDS, max(3, opp.end_sec - opp.start_sec))
    before = cut_clip(src, opp.start_sec, end, f"before_{opp.id}_{job_id}.mp4")
    after = config.MEDIA_DIR / f"after_{opp.id}_{uuid.uuid4().hex[:6]}.mp4"
    errors = []

    # 1. Replicate video-to-video
    try:
        if _try_replicate_v2v(before, brand_name, brand_desc, opp, after):
            return before, after, "video", "replicate", None
    except Exception as e:  # noqa: BLE001
        errors.append(f"replicate: {e}")

    # 2. Gemini image edit rendered to a clip
    edited = config.TMP_DIR / f"edited_{uuid.uuid4().hex[:6]}.png"
    frame = config.TMP_DIR / f"frame_{uuid.uuid4().hex[:6]}.png"
    try:
        _extract_frame(before, frame, at=_clip_duration(before) / 2)
        if _gemini_edit_image(frame, brand_name, brand_desc, opp, edited, brand_image):
            _render_clip_from_image(edited, before, after)
            return before, after, "video", "gemini-image", "; ".join(errors) or None
    except Exception as e:  # noqa: BLE001
        errors.append(f"gemini-image: {e}")
    finally:
        edited.unlink(missing_ok=True)
        frame.unlink(missing_ok=True)

    # 3. Badge overlay
    try:
        if _overlay_badge_video(before, brand_name, opp.product_to_insert, after):
            return before, after, "video", "overlay", "; ".join(errors) or None
    except Exception as e:  # noqa: BLE001
        errors.append(f"overlay: {e}")

    return before, None, "video", "none", "; ".join(errors) or "all edit methods failed"


def produce(src: Path, opp: Opportunity, brand_name: str, brand_desc: str,
            job_id: str, output_mode: str, brand_image: Optional[str] = None) -> Result:
    if output_mode == "image":
        return produce_image(src, opp, brand_name, brand_desc, job_id, brand_image)
    return produce_video(src, opp, brand_name, brand_desc, job_id, brand_image)
