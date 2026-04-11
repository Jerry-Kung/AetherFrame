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


class PromptPrecreationHistoryItem(BaseModel):
    id: str
    task_id: str
    character_id: str
    chara_name: str
    chara_avatar: str = ""
    seed_prompt: str
    prompt_count: int
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class PromptPrecreationHistoryDetailResponse(PromptPrecreationHistoryItem):
    cards: List[PromptCardItem] = Field(default_factory=list)


class PromptPrecreationHistoryListResponse(BaseModel):
    items: List[PromptPrecreationHistoryItem] = Field(default_factory=list)
    total: int = 0


class QuickCreatePromptInput(BaseModel):
    id: str = Field(default="", description="Prompt 卡片 ID")
    fullPrompt: str = Field(default="", description="Prompt 全文")


class QuickCreateStartRequest(BaseModel):
    selected_prompts: List[QuickCreatePromptInput] = Field(default_factory=list)
    n: Literal[1, 2, 3, 4] = Field(..., description="每个 Prompt 生成张数")
    aspect_ratio: Literal["16:9", "4:3", "1:1", "3:4", "9:16"] = Field(
        "16:9", description="输出图片长宽比"
    )


class QuickCreateStartResponse(BaseModel):
    task_id: str
    status: str


class QuickCreatePromptResultItem(BaseModel):
    prompt_id: str
    full_prompt: str
    attempt_count: int
    success_count: int
    requested_count: int
    generated_images: List[str] = Field(default_factory=list)


class QuickCreateStatusResponse(BaseModel):
    task_id: str
    character_id: str
    status: str
    error_message: Optional[str] = None
    current_step: Optional[str] = None
    n: int
    aspect_ratio: str
    created_at: datetime
    updated_at: datetime
    results: Optional[List[QuickCreatePromptResultItem]] = None


class QuickCreateHistoryItem(BaseModel):
    id: str
    task_id: str
    character_id: str
    chara_name: str
    chara_avatar: str = ""
    prompt_count: int
    image_count: int
    n: int
    aspect_ratio: str
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class QuickCreateHistoryDetailResponse(QuickCreateHistoryItem):
    selected_prompts: List[QuickCreatePromptInput] = Field(default_factory=list)
    results: List[QuickCreatePromptResultItem] = Field(default_factory=list)


class QuickCreateHistoryListResponse(BaseModel):
    items: List[QuickCreateHistoryItem] = Field(default_factory=list)
    total: int = 0


class ApiResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    message: Optional[str] = None
