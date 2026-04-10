"""
创作模块 — Prompt 预生成 API 模型
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field


class PromptPrecreationStartRequest(BaseModel):
    seed_prompt: str = Field(..., min_length=1, description="种子提示词")
    count: Literal[2, 3, 4] = Field(..., description="最终 Prompt 数量")


class PromptPrecreationStartResponse(BaseModel):
    task_id: str
    status: str


class PromptCardItem(BaseModel):
    """与前端 PromptCard 对齐"""

    id: str
    title: str
    preview: str
    fullPrompt: str
    tags: List[str] = Field(default_factory=list)
    createdAt: str


class PromptPrecreationStatusResponse(BaseModel):
    task_id: str
    character_id: str
    status: str
    error_message: Optional[str] = None
    current_step: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    cards: Optional[List[PromptCardItem]] = None


class ApiResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    message: Optional[str] = None
