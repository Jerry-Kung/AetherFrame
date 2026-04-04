"""
修补模块的 Pydantic 数据验证模型
"""
import logging
from pydantic import BaseModel, Field, field_validator, ConfigDict
from datetime import datetime
from typing import Optional, List, Any

logger = logging.getLogger(__name__)

# ============== 基础模型 ==============

class TaskBase(BaseModel):
    """任务基础模型"""
    name: str = Field(..., min_length=1, max_length=100, description="任务名称")
    prompt: str = Field(
        default="",
        max_length=2000,
        description="修补 Prompt（创建时可留空，在编辑区填写后再提交任务）",
    )
    output_count: int = Field(2, ge=1, le=4, description="输出数量 (1/2/4)")

    @field_validator('output_count')
    @classmethod
    def validate_output_count(cls, v):
        """验证输出数量必须是 1、2 或 4"""
        if v not in {1, 2, 4}:
            raise ValueError('output_count 必须是 1、2 或 4')
        return v

# ============== 创建模型 ==============

class TaskCreate(TaskBase):
    """创建任务请求模型"""
    pass

# ============== 更新模型 ==============

class TaskUpdate(BaseModel):
    """更新任务请求模型"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    prompt: Optional[str] = Field(None, min_length=1, max_length=2000)
    output_count: Optional[int] = Field(None, ge=1, le=4)

    @field_validator('output_count')
    @classmethod
    def validate_output_count(cls, v):
        """验证输出数量必须是 1、2 或 4（如果提供）"""
        if v is not None and v not in {1, 2, 4}:
            raise ValueError('output_count 必须是 1、2 或 4')
        return v

# ============== 响应模型 ==============

class ImageInfo(BaseModel):
    """图片信息模型"""
    filename: str
    url: str

class TaskSimple(BaseModel):
    """任务简要信息模型（用于列表）"""
    id: str
    name: str
    status: str
    prompt: str
    output_count: int
    created_at: datetime
    updated_at: datetime
    has_main_image: bool
    reference_image_count: int
    result_image_count: int

    model_config = ConfigDict(from_attributes=True)

class TaskDetail(TaskSimple):
    """任务详细信息模型"""
    error_message: Optional[str] = None
    main_image: Optional[ImageInfo] = None
    reference_images: List[ImageInfo] = []
    result_images: List[ImageInfo] = []

class TaskListResponse(BaseModel):
    """任务列表响应模型"""
    tasks: List[TaskSimple]
    total: int
    skip: int
    limit: int

# ============== 文件上传响应模型 ==============

class UploadedImageInfo(BaseModel):
    """已上传图片信息"""
    filename: str
    url: str

class FailedUploadInfo(BaseModel):
    """上传失败信息"""
    original_filename: str
    error: str

class MainImageUploadResponse(BaseModel):
    """主图上传响应"""
    filename: str
    url: str
    task_id: str

class ReferenceImagesUploadResponse(BaseModel):
    """参考图批量上传响应"""
    uploaded: List[UploadedImageInfo]
    failed: List[FailedUploadInfo]
    total: int
    task_id: str

# ============== Prompt 模板模型 ==============

class PromptTemplateBase(BaseModel):
    """模板基础模型"""
    label: str = Field(..., min_length=1, max_length=100, description="模板标签")
    text: str = Field(..., min_length=1, max_length=5000, description="模板内容")
    description: str = Field(
        default="",
        max_length=100,
        description="模板简短说明（列表展示，可选）",
    )

class PromptTemplateCreate(PromptTemplateBase):
    """创建模板请求模型"""
    pass

class PromptTemplateUpdate(BaseModel):
    """更新模板请求模型"""
    label: Optional[str] = Field(None, min_length=1, max_length=100)
    text: Optional[str] = Field(None, min_length=1, max_length=5000)
    description: Optional[str] = Field(None, max_length=100)

class PromptTemplateResponse(BaseModel):
    """模板响应模型"""
    id: str
    label: str
    description: str
    text: str
    is_builtin: bool
    sort_order: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class PromptTemplateListResponse(BaseModel):
    """模板列表响应模型"""
    templates: List[PromptTemplateResponse]
    total: int

# ============== 修补任务启动模型 ==============

class StartRepairRequest(BaseModel):
    """启动修补任务请求模型"""
    use_reference_images: bool = Field(True, description="是否使用参考图")

class StartRepairResponse(BaseModel):
    """启动修补任务响应模型"""
    task_id: str
    status: str

# ============== 任务状态响应模型 ==============

class TaskStatusResponse(BaseModel):
    """
    任务状态响应模型（用于轮询）
    """
    id: str
    status: str
    progress: Optional[int] = Field(None, ge=0, le=100, description="任务进度（预留）")
    error_message: Optional[str] = None
    updated_at: datetime
    result_images: Optional[List[ImageInfo]] = None
    
    model_config = ConfigDict(from_attributes=True)

# ============== 统一响应模型 ==============

class ApiResponse(BaseModel):
    """统一 API 响应模型"""
    success: bool
    data: Optional[Any] = None
    message: Optional[str] = None

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "success": True,
                    "data": {"id": "task_12345678", "name": "测试任务"},
                    "message": "操作成功"
                },
                {
                    "success": False,
                    "data": None,
                    "message": "错误描述信息"
                }
            ]
        }
    )

logger.debug("修补模块 Schemas 加载完成")
