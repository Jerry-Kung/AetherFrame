"""
素材加工模块 Pydantic 模型
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional, Literal

from pydantic import BaseModel, Field, ConfigDict, model_validator

RawImageType = Literal["official", "fanart"]
ShotType = Literal["full_front", "full_side", "half_front", "half_side", "face_close"]


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
    type: RawImageType = Field(..., description="official 或 fanart")
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
    official_photos: List[Optional[str]] = Field(
        default_factory=lambda: [None, None, None, None, None],
        description="标准照结果槽位，顺序: full_front/full_side/half_front/half_side/face_close",
    )
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


class StandardPhotoStartRequest(BaseModel):
    shot_type: ShotType
    aspect_ratio: Literal["16:9", "1:1", "9:16"] = "9:16"
    output_count: int = Field(2, ge=1, le=8)
    selected_raw_image_ids: List[str] = Field(default_factory=list, min_length=1)


class StandardPhotoStartResponse(BaseModel):
    task_id: str
    status: str
    shot_type: ShotType
    aspect_ratio: str
    output_count: int


class StandardPhotoStatusResponse(BaseModel):
    task_id: str
    character_id: str
    shot_type: ShotType
    aspect_ratio: str
    output_count: int
    status: str
    error_message: Optional[str] = None
    selected_raw_image_ids: List[str] = Field(default_factory=list)
    result_images: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class StandardPhotoSelectRequest(BaseModel):
    selected_result_filename: Optional[str] = None
    selected_result_index: Optional[int] = Field(None, ge=0)

    @model_validator(mode="after")
    def check_one_selected(self):
        if self.selected_result_filename is None and self.selected_result_index is None:
            raise ValueError("selected_result_filename 或 selected_result_index 至少提供一个")
        return self


class CharaProfileStartRequest(BaseModel):
    selected_fanart_ids: List[str] = Field(
        ...,
        min_length=1,
        max_length=5,
        description="选中的同人立绘 raw image id，1–5 个",
    )


class CharaProfileStartResponse(BaseModel):
    task_id: str
    status: str


class CharaProfileStatusResponse(BaseModel):
    task_id: str
    character_id: str
    status: str
    error_message: Optional[str] = None
    current_step: Optional[str] = None
    selected_fanart_ids: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class BioPatchRequest(BaseModel):
    chara_profile: Optional[str] = Field(None, description="角色小档案全文（Markdown）")
    creative_advice: Optional[str] = Field(None, description="创作建议全文")

    @model_validator(mode="after")
    def at_least_one_field(self):
        if self.chara_profile is None and self.creative_advice is None:
            raise ValueError("至少提供 chara_profile 或 creative_advice 之一")
        return self
