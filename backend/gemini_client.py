"""Wraps google-genai for video analysis (and shared client creation)."""
import base64
import json
import re
import time
import uuid
from typing import List, Optional, Tuple

from google import genai
from google.genai import types

import config
from models import Opportunity

_client = None


def decode_image(data: Optional[str]) -> Optional[Tuple[bytes, str]]:
    """Decode a base64 image (raw or data: URL) into (bytes, mime). None if empty/bad."""
    if not data:
        return None
    mime = "image/png"
    try:
        if data.startswith("data:"):
            header, b64 = data.split(",", 1)
            mime = header[5:].split(";")[0] or mime
            data = b64
        return base64.b64decode(data), mime
    except Exception:
        return None


def get_client():
    """Lazily create a Vertex AI genai client (mirrors the user's snippet)."""
    global _client
    if _client is None:
        if not config.GOOGLE_API_KEY:
            raise RuntimeError(
                "GOOGLE_API_KEY missing. Add it to the project .env file."
            )
        _client = genai.Client(vertexai=True, api_key=config.GOOGLE_API_KEY)
    return _client


def extract_video_id(url: str) -> str:
    """Pull the 11-char YouTube id from any common URL form."""
    patterns = [
        r"(?:v=|/shorts/|youtu\.be/|/embed/|/v/)([A-Za-z0-9_-]{11})",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    # Maybe they pasted a bare id
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", url.strip()):
        return url.strip()
    raise ValueError(f"Could not parse a YouTube video id from: {url}")


_SAFETY = [
    types.SafetySetting(category=c, threshold="OFF")
    for c in (
        "HARM_CATEGORY_HATE_SPEECH",
        "HARM_CATEGORY_DANGEROUS_CONTENT",
        "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "HARM_CATEGORY_HARASSMENT",
    )
]


def _is_resource_exhausted(error: Exception) -> bool:
    message = str(error).lower()
    return "resource_exhausted" in message or "429" in message or "quota" in message


def generate_with_retry(client, *, model: str, contents, request_config):
    """Retry Gemini quota throttling up to three times, three seconds apart."""
    last_error = None
    for attempt in range(3):
        try:
            return client.models.generate_content(
                model=model, contents=contents, config=request_config
            )
        except Exception as exc:  # noqa: BLE001 - SDK exception types vary by version
            last_error = exc
            if not _is_resource_exhausted(exc) or attempt == 2:
                raise
            time.sleep(3)
    raise last_error  # pragma: no cover - loop either returns or raises


def _build_prompt(brand_name: str, brand_desc: str, clip_seconds: int) -> str:
    return f"""You are an expert at native/seamless brand integration for YouTube videos.

A creator wants to integrate a NEW brand into THIS existing video.

NEW BRAND: {brand_name}
ABOUT THE BRAND: {brand_desc or "(no description provided)"}

Watch the video and identify the 3-5 BEST moments where this brand's product could be
seamlessly inserted so it feels native to the scene (e.g. placed on a desk, held by the
creator, visible in the background, referenced naturally).

For each opportunity return a window of about {clip_seconds} seconds (end_sec - start_sec
should be <= {clip_seconds}).

Respond with ONLY a JSON array (no markdown, no prose). Each element:
{{
  "start_sec": <number, seconds from start>,
  "end_sec": <number, seconds from start>,
  "scene_summary": "<what is happening on screen>",
  "why_it_fits": "<why this brand fits naturally here>",
  "integration_idea": "<concretely how/where to place the product>",
  "product_to_insert": "<the specific product object to insert>",
  "placement_confidence": <integer 0-100, confidence this product can be placed naturally>
}}
"""


def _parse_opportunities(text: str, clip_seconds: int) -> List[Opportunity]:
    # Strip code fences if the model added them
    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    # Grab the outermost JSON array
    start, end = cleaned.find("["), cleaned.rfind("]")
    if start != -1 and end != -1:
        cleaned = cleaned[start : end + 1]
    data = json.loads(cleaned)

    opportunities: List[Opportunity] = []
    for item in data:
        start_sec = float(item.get("start_sec", 0))
        end_sec = float(item.get("end_sec", start_sec + clip_seconds))
        # Clamp window length
        if end_sec - start_sec > clip_seconds:
            end_sec = start_sec + clip_seconds
        if end_sec <= start_sec:
            end_sec = start_sec + clip_seconds
        try:
            placement_confidence = round(float(item.get("placement_confidence", 75)))
        except (TypeError, ValueError):
            placement_confidence = 75
        opportunities.append(
            Opportunity(
                id=uuid.uuid4().hex[:8],
                start_sec=round(start_sec, 2),
                end_sec=round(end_sec, 2),
                scene_summary=item.get("scene_summary", ""),
                why_it_fits=item.get("why_it_fits", ""),
                integration_idea=item.get("integration_idea", ""),
                product_to_insert=item.get("product_to_insert", f"{item.get('product_to_insert','')}"),
                placement_confidence=max(0, min(100, placement_confidence)),
            )
        )
    return opportunities


def analyze_video(youtube_url: str, brand_name: str, brand_desc: str,
                  brand_image: Optional[str] = None) -> List[Opportunity]:
    """Send the YouTube URL to Gemini and return structured ad-integration opportunities."""
    client = get_client()
    video_part = types.Part.from_uri(file_uri=youtube_url, mime_type="video/mp4")
    prompt = _build_prompt(brand_name, brand_desc, config.CLIP_SECONDS)

    parts = [video_part]
    ref = decode_image(brand_image)
    if ref is not None:
        parts.append(types.Part.from_bytes(data=ref[0], mime_type=ref[1]))
        prompt += "\n\nA reference image of the brand's product is attached — use it to understand the product."
    parts.append(types.Part(text=prompt))

    contents = [types.Content(role="user", parts=parts)]
    cfg = types.GenerateContentConfig(
        temperature=1,
        top_p=0.95,
        max_output_tokens=65535,
        safety_settings=_SAFETY,
        response_mime_type="application/json",
        thinking_config=types.ThinkingConfig(thinking_level="MEDIUM"),
    )

    resp = generate_with_retry(
        client, model=config.ANALYSIS_MODEL, contents=contents, request_config=cfg
    )
    return _parse_opportunities(resp.text, config.CLIP_SECONDS)
