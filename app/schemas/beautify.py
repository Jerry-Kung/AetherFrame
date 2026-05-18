from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class BeautifyStartBody(BaseModel):
    source_kind: Literal["quick_create", "repair"]
    source_task_id: str
    source_image_path: str


class BeautifyTaskStatusData(BaseModel):
    task_id: str
    source_kind: str
    source_task_id: str
    source_image_path: str
    status: str
    current_step: Optional[str] = None
    error_message: Optional[str] = None
    beautified_filename: Optional[str] = None
    beautified_url: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class BeautifyDeleteData(BaseModel):
    deleted_id: str


class ApiResponse(BaseModel):
    success: bool
    data: Optional[object] = None
    message: Optional[str] = None
