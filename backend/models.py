"""Pydantic schemas shared across the API."""
from typing import List, Optional

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    youtube_url: str
    brand_name: str
    brand_description: str = ""
    brand_image: Optional[str] = None   # base64 (raw or data: URL) reference image


class Opportunity(BaseModel):
    id: str
    start_sec: float
    end_sec: float
    scene_summary: str
    why_it_fits: str
    integration_idea: str
    product_to_insert: str
    placement_confidence: int = Field(default=75, ge=0, le=100)
    frame_url: Optional[str] = None


class AnalyzeResponse(BaseModel):
    video_id: str
    opportunities: List[Opportunity]


class GenerateRequest(BaseModel):
    youtube_url: str
    brand_name: str
    brand_description: str = ""
    brand_image: Optional[str] = None
    opportunities: List[Opportunity]
    output_mode: str = "image"        # "image" (cheap) | "video" (Replicate v2v)


class PlacementBox(BaseModel):
    """A normalized target region drawn by an operator."""
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)


class RefineRequest(BaseModel):
    before_url: str
    brand_name: str
    brand_description: str = ""
    brand_image: Optional[str] = None
    opportunity: Opportunity
    placement: PlacementBox
    feedback: str = ""
    job_id: Optional[str] = None
    clip_index: Optional[int] = Field(default=None, ge=0)


class RefineResponse(BaseModel):
    after_url: str


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
    share_token: str
    youtube_url: str = ""
    brand_name: str = ""
    brand_description: str = ""
    status: str = "queued"            # queued | running | done | error
    progress: float = 0.0            # 0..1
    message: str = ""
    clips: List[ClipResult] = []
    error: Optional[str] = None
