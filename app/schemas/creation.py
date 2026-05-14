"""
创作模块 — Prompt 预生成 API 模型
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class PromptPrecreationChainQuickCreate(BaseModel):
    """预生成完成后自动启动一键创作（与默认配置一致）"""

    n: Literal[1, 2, 3, 4] = Field(..., description="每个 Prompt 生成张数")
    aspect_ratio: Literal["16:9", "4:3", "1:1", "3:4", "9:16"] = Field(
        ..., description="输出图片长宽比"
    )
    max_prompts: Literal[1, 2, 3, 4] = Field(
        ..., description="提交到一键创作的 Prompt 条数上限（不超过本次生成数量）"
    )


class PromptPrecreationStartRequest(BaseModel):
    seed_prompt: str = Field(..., min_length=1, description="种子提示词")
    count: Literal[1, 2, 3, 4] = Field(..., description="最终 Prompt 数量")
    chain_quick_create: Optional[PromptPrecreationChainQuickCreate] = Field(
        default=None,
        description="若设置，则在预生成成功后自动创建一键创作任务",
    )

    @model_validator(mode="after")
    def validate_chain_vs_count(self) -> "PromptPrecreationStartRequest":
        if self.chain_quick_create is not None:
            if self.chain_quick_create.max_prompts > self.count:
                raise ValueError("chain_quick_create.max_prompts 不能大于 count")
        return self


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
    chained_quick_create_task_id: Optional[str] = None
    chain_error: Optional[str] = None


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


class QuickCreateImageReview(BaseModel):
    """一键创作单图审核结果（仅 usable / repair_needed 会出现在成功结果中）"""

    status: Literal["usable", "repair_needed"]
    overall_quality: int = Field(..., ge=0, le=100)
    summary: str = ""
    major_issues: List[str] = Field(default_factory=list)
    optimization_suggestions: List[str] = Field(default_factory=list)


class QuickCreateGeneratedImage(BaseModel):
    """相对 task 工作目录的图片路径，及可选的审核详情（旧数据可能无 review）"""

    path: str
    review: Optional[QuickCreateImageReview] = None


class QuickCreatePromptResultItem(BaseModel):
    prompt_id: str
    full_prompt: str
    attempt_count: int
    success_count: int
    requested_count: int
    generated_images: List[QuickCreateGeneratedImage] = Field(default_factory=list)

    @field_validator("generated_images", mode="before")
    @classmethod
    def coerce_generated_images(cls, raw: Any) -> List[Any]:
        if not isinstance(raw, list):
            return []
        out: List[Dict[str, Any]] = []
        for item in raw:
            if isinstance(item, str):
                p = item.strip().replace("\\", "/")
                if p:
                    out.append({"path": p, "review": None})
            elif isinstance(item, dict):
                p = str(item.get("path") or item.get("relative_path") or "").strip().replace("\\", "/")
                if not p:
                    continue
                rev = item.get("review")
                out.append({"path": p, "review": rev})
        return out


class QuickCreateStatusResponse(BaseModel):
    task_id: str
    character_id: str
    seed_prompt: str
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
    seed_prompt: str
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


class BatchAutomationStartRequest(BaseModel):
    """首页批量自动化创作提交"""

    iterations: int = Field(..., ge=2, le=10, description="创作内容条数")
    prompt_count: Literal[1, 2, 3, 4] = Field(..., description="Prompt 预生成数量")
    images_per_prompt: Literal[1, 2, 3, 4] = Field(..., description="每个 Prompt 生成图片数")
    aspect_ratio: Literal["16:9", "4:3", "1:1", "3:4", "9:16"] = Field(..., description="图片长宽比")
    max_prompts: Literal[1, 2, 3, 4] = Field(
        ...,
        description="提交一键创作的 Prompt 条数上限（不超过 prompt_count）",
    )
    character_ids: Optional[List[str]] = Field(
        default=None,
        description="指定角色 ID；不传或空列表表示全部资料已完善角色",
    )

    @model_validator(mode="after")
    def validate_max_prompts_vs_count(self) -> "BatchAutomationStartRequest":
        if self.max_prompts > self.prompt_count:
            raise ValueError("max_prompts 不能大于 prompt_count")
        return self


class BatchAutomationStartResponse(BaseModel):
    run_id: str
    status: str


class BatchAutomationItemOut(BaseModel):
    id: str
    run_id: str
    step_index: int
    character_id: str
    chara_name: str
    chara_avatar: str = ""
    seed_prompt_id: str
    seed_section: str
    seed_prompt_text: str
    prompt_precreation_task_id: Optional[str] = None
    quick_create_task_id: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class BatchAutomationRunListItemOut(BatchAutomationItemOut):
    """列表接口在条目上附带所属 run 状态"""

    run_status: str


class BatchAutomationRunDetailResponse(BaseModel):
    id: str
    status: str
    iterations_total: int
    iterations_done: int
    config: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    items: List[BatchAutomationItemOut] = Field(default_factory=list)


class BatchAutomationItemListResponse(BaseModel):
    items: List[BatchAutomationRunListItemOut] = Field(default_factory=list)
    total: int = 0
