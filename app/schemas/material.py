"""
素材加工模块 Pydantic 模型
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field, ConfigDict, model_validator


class CharacterCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    display_name: Optional[str] = Field(None, max_length=200)


class CharacterUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    display_name: Optional[str] = Field(None, max_length=200)

    @model_validator(mode="after")
    def at_least_one_field(self):
        if self.name is None and self.display_name is None:
            raise ValueError("至少提供 name 或 display_name 之一")
        return self


class SettingTextUpdate(BaseModel):
    setting_text: str = Field(..., description="角色设定全文（UTF-8）")


class RawImageTagsUpdate(BaseModel):
    tags: List[str] = Field(default_factory=list)


class RawImageItem(BaseModel):
    id: str
    url: str
    tags: List[str]


class RawImageUploadFail(BaseModel):
    original_filename: str
    error: str


class RawImagesUploadData(BaseModel):
    uploaded: List[RawImageItem]
    failed: List[RawImageUploadFail]
    total: int
    character_id: str


class CharacterSummary(BaseModel):
    id: str
    name: str
    display_name: str
    status: str
    updated_at: datetime
    raw_image_count: int
    setting_preview: str
    avatar_url: str = ""

    model_config = ConfigDict(from_attributes=True)


class CharacterDetail(BaseModel):
    id: str
    name: str
    display_name: str
    avatar_url: str
    status: str
    updated_at: datetime
    setting_text: str
    raw_images: List[RawImageItem]
    official_photos: List[Optional[str]]
    bio: dict

    model_config = ConfigDict(from_attributes=True)


class CharacterListData(BaseModel):
    characters: List[CharacterSummary]
    total: int
    skip: int
    limit: int


class ApiResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    message: Optional[str] = None

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"success": True, "data": {"id": "mchar_abc"}, "message": "ok"}
            ]
        }
    )
