"""
Schemas 模块 - Pydantic 数据验证模型
"""
from app.schemas.repair import (
    TaskBase,
    TaskCreate,
    TaskUpdate,
    ImageInfo,
    TaskSimple,
    TaskDetail,
    TaskListResponse,
    UploadedImageInfo,
    FailedUploadInfo,
    MainImageUploadResponse,
    ReferenceImagesUploadResponse,
    PromptTemplateBase,
    PromptTemplateCreate,
    PromptTemplateUpdate,
    PromptTemplateResponse,
    PromptTemplateListResponse,
    ApiResponse
)

__all__ = [
    "TaskBase",
    "TaskCreate",
    "TaskUpdate",
    "ImageInfo",
    "TaskSimple",
    "TaskDetail",
    "TaskListResponse",
    "UploadedImageInfo",
    "FailedUploadInfo",
    "MainImageUploadResponse",
    "ReferenceImagesUploadResponse",
    "PromptTemplateBase",
    "PromptTemplateCreate",
    "PromptTemplateUpdate",
    "PromptTemplateResponse",
    "PromptTemplateListResponse",
    "ApiResponse"
]
