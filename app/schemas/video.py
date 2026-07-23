from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class ApiResponse(BaseModel):
    success: bool
    data: Optional[object] = None
    message: Optional[str] = None


class VideoImportBody(BaseModel):
    source_kind: Literal["quick_create"]
    source_task_id: str
    source_image_path: str
    ref_prompt_text: Optional[str] = None


class PromptJobBody(BaseModel):
    mode: Literal["recommend", "optimize"]
    manual_prompt: Optional[str] = None


class VideoSubmitBody(BaseModel):
    video_prompt_text: str
    image_role: Literal["first_frame", "reference_image"] = "first_frame"
    duration: int = Field(default=8, ge=4, le=15)
    generate_audio: bool = False
    ratio: str


class VideoTaskData(BaseModel):
    task_id: str
    source_kind: str
    status: str
    image_role: str
    duration: int
    generate_audio: bool
    ratio: str
    ref_prompt_text: Optional[str] = None
    video_prompt_text: Optional[str] = None
    prompt_mode: Optional[str] = None
    prompt_job_status: Optional[str] = None
    prompt_job_result: Optional[str] = None
    prompt_job_error: Optional[str] = None
    video_filename: Optional[str] = None
    error_message: Optional[str] = None
    recommended_ratio: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
