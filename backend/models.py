"""Pydantic schemas shared across the API."""
from typing import List, Optional

from pydantic import BaseModel


class AnalyzeRequest(BaseModel):
    youtube_url: str
    brand_name: str
    brand_description: str = ""


class Opportunity(BaseModel):
    id: str
    start_sec: float
    end_sec: float
    scene_summary: str
    why_it_fits: str
    integration_idea: str
    product_to_insert: str
    frame_url: Optional[str] = None


class AnalyzeResponse(BaseModel):
    video_id: str
    opportunities: List[Opportunity]


class GenerateRequest(BaseModel):
    youtube_url: str
    brand_name: str
    brand_description: str = ""
    opportunities: List[Opportunity]
    output_mode: str = "image"        # "image" (cheap) | "video" (Replicate v2v)


class ClipResult(BaseModel):
    opportunity: Opportunity
    before_url: Optional[str] = None
    after_url: Optional[str] = None
    media_kind: str = "video"         # "image" | "video"
    edit_method: str = "pending"      # replicate | gemini-image | overlay | none
    edit_failed: bool = False
    error: Optional[str] = None


class Job(BaseModel):
    job_id: str
    status: str = "queued"            # queued | running | done | error
    progress: float = 0.0            # 0..1
    message: str = ""
    clips: List[ClipResult] = []
    error: Optional[str] = None
