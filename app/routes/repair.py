"""
修补模块 API 路由
"""
import logging
import os
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.schemas.repair import (
    TaskCreate,
    TaskUpdate,
    ApiResponse,
    UploadedImageInfo,
    FailedUploadInfo,
    MainImageUploadResponse,
    ReferenceImagesUploadResponse,
    PromptTemplateCreate,
    PromptTemplateUpdate,
    PromptTemplateResponse,
    PromptTemplateListResponse,
    StartRepairRequest,
    StartRepairResponse
)
from app.services.repair_service import RepairService, RepairTaskService
from app.services.file_service import FileValidationError, FileSaveError, FileDeleteError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/repair", tags=["repair"])


# ==========================================
# 依赖注入
# ==========================================

def get_repair_service(db: Session = Depends(get_db)) -> RepairService:
    """获取 RepairService 实例"""
    return RepairService(db)


def get_repair_task_service(db: Session = Depends(get_db)) -> RepairTaskService:
    """获取 RepairTaskService 实例"""
    return RepairTaskService(db)


# ==========================================
# 任务管理接口
# ==========================================

@router.get("/tasks", response_model=ApiResponse)
@router.get("/tasks/", response_model=ApiResponse)
async def list_tasks(
    skip: int = Query(0, ge=0, description="跳过数量"),
    limit: int = Query(50, ge=1, le=100, description="返回数量"),
    order_by: str = Query("created_at", description="排序字段"),
    order_dir: str = Query("desc", description="排序方向 (asc/desc)"),
    status: Optional[str] = Query(None, description="按状态过滤"),
    repair_service: RepairService = Depends(get_repair_service)
):
    """
    获取任务列表

    支持分页、排序和状态过滤
    """
    logger.info(
        f"API 请求 - 获取任务列表: skip={skip}, limit={limit}, "
        f"order_by={order_by}, order_dir={order_dir}, status={status}"
    )

    try:
        # 验证排序方向
        if order_dir not in {"asc", "desc"}:
            raise HTTPException(status_code=400, detail="order_dir 必须是 'asc' 或 'desc'")

        # 验证排序字段
        valid_order_fields = {"id", "name", "status", "created_at", "updated_at"}
        if order_by not in valid_order_fields:
            raise HTTPException(
                status_code=400,
                detail=f"order_by 必须是以下之一: {', '.join(valid_order_fields)}"
            )

        # 验证状态（如果提供）
        if status and status not in {"pending", "processing", "completed", "failed"}:
            raise HTTPException(
                status_code=400,
                detail="status 必须是 pending、processing、completed 或 failed"
            )

        tasks, total = repair_service.list_tasks(
            skip=skip,
            limit=limit,
            order_by=order_by,
            order_dir=order_dir,
            status=status
        )

        response_data = repair_service.build_task_list_response(tasks, total, skip, limit)

        logger.info(f"API 响应 - 获取任务列表成功: 返回 {len(tasks)} 个任务，总计 {total} 个")

        return ApiResponse(
            success=True,
            data=response_data.model_dump(),
            message="获取任务列表成功"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API 错误 - 获取任务列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取任务列表失败")


@router.post("/tasks", response_model=ApiResponse)
@router.post("/tasks/", response_model=ApiResponse)
async def create_task(
    task_data: TaskCreate,
    repair_service: RepairService = Depends(get_repair_service)
):
    """
    创建新任务
    """
    logger.info(f"API 请求 - 创建任务: name={task_data.name}")

    try:
        task = repair_service.create_task(task_data)
        task_simple = repair_service.build_task_simple_response(task)

        logger.info(f"API 响应 - 创建任务成功: task_id={task.id}")

        return ApiResponse(
            success=True,
            data=task_simple.model_dump(),
            message="任务创建成功"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API 错误 - 创建任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="创建任务失败")


@router.get("/tasks/{task_id}", response_model=ApiResponse)
async def get_task(
    task_id: str,
    repair_service: RepairService = Depends(get_repair_service)
):
    """
    获取任务详情
    """
    logger.info(f"API 请求 - 获取任务详情: task_id={task_id}")

    try:
        task = repair_service.get_task(task_id)
        if not task:
            logger.warning(f"API 响应 - 任务不存在: task_id={task_id}")
            raise HTTPException(status_code=404, detail="任务不存在")

        task_detail = repair_service.build_task_detail_response(task)

        logger.info(f"API 响应 - 获取任务详情成功: task_id={task_id}")

        return ApiResponse(
            success=True,
            data=task_detail.model_dump(),
            message="获取任务详情成功"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API 错误 - 获取任务详情失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取任务详情失败")


@router.put("/tasks/{task_id}", response_model=ApiResponse)
async def update_task(
    task_id: str,
    task_data: TaskUpdate,
    repair_service: RepairService = Depends(get_repair_service)
):
    """
    更新任务信息

    processing 状态不可更新；pending、completed、failed 可更新名称、prompt、输出数量等
    """
    logger.info(f"API 请求 - 更新任务: task_id={task_id}")

    try:
        task = repair_service.get_task(task_id)
        if not task:
            logger.warning(f"API 响应 - 任务不存在: task_id={task_id}")
            raise HTTPException(status_code=404, detail="任务不存在")

        updated_task = repair_service.update_task(task_id, task_data)
        if not updated_task:
            if task.status == "processing":
                raise HTTPException(
                    status_code=409,
                    detail=f"任务状态不允许更新，当前状态: {task.status}"
                )
            raise HTTPException(status_code=400, detail="没有提供有效的更新字段")

        task_simple = repair_service.build_task_simple_response(updated_task)

        logger.info(f"API 响应 - 更新任务成功: task_id={task_id}")

        return ApiResponse(
            success=True,
            data=task_simple.model_dump(),
            message="任务更新成功"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API 错误 - 更新任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="更新任务失败")


@router.delete("/tasks/{task_id}", response_model=ApiResponse)
async def delete_task(
    task_id: str,
    repair_service: RepairService = Depends(get_repair_service)
):
    """
    删除任务及其所有文件
    """
    logger.info(f"API 请求 - 删除任务: task_id={task_id}")

    try:
        task = repair_service.get_task(task_id)
        if not task:
            logger.warning(f"API 响应 - 任务不存在: task_id={task_id}")
            raise HTTPException(status_code=404, detail="任务不存在")

        try:
            success = repair_service.delete_task(task_id)
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e))

        if not success:
            raise HTTPException(
                status_code=500,
                detail="删除任务失败：本地文件未能完全清理，数据库记录未删除",
            )

        logger.info(f"API 响应 - 删除任务成功: task_id={task_id}")

        return ApiResponse(
            success=True,
            data=None,
            message="任务删除成功"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API 错误 - 删除任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="删除任务失败")


# ==========================================
# 文件上传接口
# ==========================================

@router.post("/tasks/{task_id}/main-image", response_model=ApiResponse)
async def upload_main_image(
    task_id: str,
    file: UploadFile = File(...),
    repair_service: RepairService = Depends(get_repair_service)
):
    """
    上传主图
    
    支持格式：PNG、JPG/JPEG、WebP
    文件大小限制：最大 10MB
    """
    logger.info(f"API 请求 - 上传主图: task_id={task_id}, filename={file.filename}")

    try:
        filename, url = repair_service.upload_main_image(task_id, file)
        
        response_data = MainImageUploadResponse(
            filename=filename,
            url=url,
            task_id=task_id
        )

        logger.info(f"API 响应 - 主图上传成功: task_id={task_id}, filename={filename}")

        return ApiResponse(
            success=True,
            data=response_data.model_dump(),
            message="主图上传成功"
        )

    except ValueError as e:
        if str(e) == "任务不存在":
            logger.warning(f"API 响应 - 任务不存在: task_id={task_id}")
            raise HTTPException(status_code=404, detail="任务不存在")
        raise
    except FileValidationError as e:
        logger.warning(f"API 响应 - 文件验证失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except FileSaveError as e:
        logger.error(f"API 错误 - 文件保存失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="文件保存失败")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API 错误 - 上传主图失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="上传主图失败")


@router.post("/tasks/{task_id}/reference-images", response_model=ApiResponse)
async def upload_reference_images(
    task_id: str,
    files: List[UploadFile] = File(...),
    repair_service: RepairService = Depends(get_repair_service)
):
    """
    批量上传参考图
    
    支持格式：PNG、JPG/JPEG、WebP
    文件大小限制：每张最大 10MB
    """
    logger.info(f"API 请求 - 批量上传参考图: task_id={task_id}, count={len(files)}")

    try:
        uploaded, failed = repair_service.upload_reference_images(task_id, files)
        
        response_data = ReferenceImagesUploadResponse(
            uploaded=uploaded,
            failed=failed,
            total=len(files),
            task_id=task_id
        )

        message = f"成功上传 {len(uploaded)} 张参考图"
        if failed:
            message += f"，{len(failed)} 张失败"

        logger.info(f"API 响应 - 批量上传参考图完成: task_id={task_id}, 成功={len(uploaded)}, 失败={len(failed)}")

        return ApiResponse(
            success=True,
            data=response_data.model_dump(),
            message=message
        )

    except ValueError as e:
        if str(e) == "任务不存在":
            logger.warning(f"API 响应 - 任务不存在: task_id={task_id}")
            raise HTTPException(status_code=404, detail="任务不存在")
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API 错误 - 批量上传参考图失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="批量上传参考图失败")


@router.get("/tasks/{task_id}/images/{image_type}/{filename}")
async def get_image(
    task_id: str,
    image_type: str,
    filename: str,
    repair_service: RepairService = Depends(get_repair_service)
):
    """
    获取图片文件
    
    image_type: main/reference/result
    """
    logger.debug(f"API 请求 - 获取图片: task_id={task_id}, image_type={image_type}, filename={filename}")

    try:
        # 验证 image_type
        valid_image_types = {"main", "reference", "result"}
        if image_type not in valid_image_types:
            raise HTTPException(
                status_code=400,
                detail=f"image_type 必须是以下之一: {', '.join(valid_image_types)}"
            )

        file_path = repair_service.get_image_path(task_id, image_type, filename)
        
        if not file_path:
            logger.warning(f"API 响应 - 文件不存在: task_id={task_id}, image_type={image_type}, filename={filename}")
            raise HTTPException(status_code=404, detail="文件不存在")

        # 根据文件扩展名设置 Content-Type
        ext = os.path.splitext(filename)[1].lower()
        media_type_map = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp"
        }
        media_type = media_type_map.get(ext, "application/octet-stream")

        logger.debug(f"API 响应 - 返回图片: {file_path}")

        return FileResponse(
            path=file_path,
            media_type=media_type,
            filename=filename
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API 错误 - 获取图片失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取图片失败")


@router.delete("/tasks/{task_id}/main-image", response_model=ApiResponse)
async def delete_main_image(
    task_id: str,
    repair_service: RepairService = Depends(get_repair_service)
):
    """
    删除主图
    """
    logger.info(f"API 请求 - 删除主图: task_id={task_id}")

    try:
        success = repair_service.delete_main_image(task_id)
        
        if not success:
            # 检查任务是否存在
            task = repair_service.get_task(task_id)
            if not task:
                raise HTTPException(status_code=404, detail="任务不存在")

        logger.info(f"API 响应 - 主图删除成功: task_id={task_id}")

        return ApiResponse(
            success=True,
            data=None,
            message="主图删除成功"
        )

    except HTTPException:
        raise
    except FileDeleteError as e:
        logger.error(f"API 错误 - 主图删除失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="主图删除失败")
    except Exception as e:
        logger.error(f"API 错误 - 删除主图失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="删除主图失败")


@router.delete("/tasks/{task_id}/reference-images/{filename}", response_model=ApiResponse)
async def delete_reference_image(
    task_id: str,
    filename: str,
    repair_service: RepairService = Depends(get_repair_service)
):
    """
    删除参考图
    """
    logger.info(f"API 请求 - 删除参考图: task_id={task_id}, filename={filename}")

    try:
        success = repair_service.delete_reference_image(task_id, filename)
        
        if not success:
            # 检查任务是否存在
            task = repair_service.get_task(task_id)
            if not task:
                raise HTTPException(status_code=404, detail="任务不存在")

        logger.info(f"API 响应 - 参考图删除成功: task_id={task_id}, filename={filename}")

        return ApiResponse(
            success=True,
            data=None,
            message="参考图删除成功"
        )

    except HTTPException:
        raise
    except FileDeleteError as e:
        logger.error(f"API 错误 - 参考图删除失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="参考图删除失败")
    except Exception as e:
        logger.error(f"API 错误 - 删除参考图失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="删除参考图失败")


# ==========================================
# Prompt 模板接口
# ==========================================

@router.get("/templates", response_model=ApiResponse)
async def list_templates(
    template_type: Optional[str] = Query(None, description="模板类型 (builtin/custom)"),
    repair_service: RepairService = Depends(get_repair_service)
):
    """
    获取模板列表
    
    内置模板在前，自定义模板在后
    """
    logger.info(f"API 请求 - 获取模板列表: template_type={template_type}")

    try:
        # 验证 template_type
        if template_type and template_type not in {"builtin", "custom"}:
            raise HTTPException(
                status_code=400,
                detail="template_type 必须是 'builtin' 或 'custom'"
            )

        templates = repair_service.list_templates(template_type)
        response_data = repair_service.build_template_list_response(templates)

        logger.info(f"API 响应 - 获取模板列表成功: 返回 {len(templates)} 个模板")

        return ApiResponse(
            success=True,
            data=response_data.model_dump(),
            message="获取模板列表成功"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API 错误 - 获取模板列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取模板列表失败")


@router.post("/templates", response_model=ApiResponse)
async def create_template(
    template_data: PromptTemplateCreate,
    repair_service: RepairService = Depends(get_repair_service)
):
    """
    创建自定义模板
    """
    logger.info(f"API 请求 - 创建模板: label={template_data.label}")

    try:
        template = repair_service.create_template(template_data)
        template_response = repair_service.build_template_response(template)

        logger.info(f"API 响应 - 创建模板成功: template_id={template.id}")

        return ApiResponse(
            success=True,
            data=template_response.model_dump(),
            message="模板创建成功"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API 错误 - 创建模板失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="创建模板失败")


@router.get("/templates/{template_id}", response_model=ApiResponse)
async def get_template(
    template_id: str,
    repair_service: RepairService = Depends(get_repair_service)
):
    """
    获取模板详情
    """
    logger.info(f"API 请求 - 获取模板详情: template_id={template_id}")

    try:
        template = repair_service.get_template(template_id)
        if not template:
            logger.warning(f"API 响应 - 模板不存在: template_id={template_id}")
            raise HTTPException(status_code=404, detail="模板不存在")

        template_response = repair_service.build_template_response(template)

        logger.info(f"API 响应 - 获取模板详情成功: template_id={template_id}")

        return ApiResponse(
            success=True,
            data=template_response.model_dump(),
            message="获取模板详情成功"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API 错误 - 获取模板详情失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取模板详情失败")


@router.put("/templates/{template_id}", response_model=ApiResponse)
async def update_template(
    template_id: str,
    template_data: PromptTemplateUpdate,
    repair_service: RepairService = Depends(get_repair_service)
):
    """
    更新模板（仅允许更新自定义模板）
    """
    logger.info(f"API 请求 - 更新模板: template_id={template_id}")

    try:
        template = repair_service.get_template(template_id)
        if not template:
            logger.warning(f"API 响应 - 模板不存在: template_id={template_id}")
            raise HTTPException(status_code=404, detail="模板不存在")

        updated_template = repair_service.update_template(template_id, template_data)
        if not updated_template:
            if template.is_builtin:
                raise HTTPException(
                    status_code=409,
                    detail="内置模板不允许更新"
                )
            raise HTTPException(status_code=400, detail="没有提供有效的更新字段")

        template_response = repair_service.build_template_response(updated_template)

        logger.info(f"API 响应 - 更新模板成功: template_id={template_id}")

        return ApiResponse(
            success=True,
            data=template_response.model_dump(),
            message="模板更新成功"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API 错误 - 更新模板失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="更新模板失败")


@router.delete("/templates/{template_id}", response_model=ApiResponse)
async def delete_template(
    template_id: str,
    repair_service: RepairService = Depends(get_repair_service)
):
    """
    删除模板（仅允许删除自定义模板）
    """
    logger.info(f"API 请求 - 删除模板: template_id={template_id}")

    try:
        template = repair_service.get_template(template_id)
        if not template:
            logger.warning(f"API 响应 - 模板不存在: template_id={template_id}")
            raise HTTPException(status_code=404, detail="模板不存在")

        success = repair_service.delete_template(template_id)
        if not success:
            if template.is_builtin:
                raise HTTPException(
                    status_code=409,
                    detail="内置模板不允许删除"
                )
            raise HTTPException(status_code=500, detail="删除模板失败")

        logger.info(f"API 响应 - 删除模板成功: template_id={template_id}")

        return ApiResponse(
            success=True,
            data=None,
            message="模板删除成功"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API 错误 - 删除模板失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="删除模板失败")


# ==========================================
# 修补任务处理接口
# ==========================================

@router.post("/tasks/{task_id}/start", response_model=ApiResponse)
async def start_repair_task(
    task_id: str,
    request: StartRepairRequest,
    background_tasks: BackgroundTasks,
    task_service: RepairTaskService = Depends(get_repair_task_service),
):
    """
    启动修补任务（异步）

    允许 pending、completed、failed 启动；processing 不可重复启动。
    completed/failed 再次启动时会先清空 results 目录再执行。
    须已上传主图并填写 prompt。
    """
    logger.info(f"API 请求 - 启动修补任务: task_id={task_id}, use_reference_images={request.use_reference_images}")

    try:
        task = await task_service.start_task(
            task_id=task_id,
            use_reference_images=request.use_reference_images,
            background_tasks=background_tasks
        )

        response_data = StartRepairResponse(
            task_id=task_id,
            status=task.status
        )

        logger.info(f"API 响应 - 修补任务启动成功: task_id={task_id}, status={task.status}")
        return ApiResponse(
            success=True,
            data=response_data.model_dump(),
            message="任务已开始处理"
        )

    except ValueError as e:
        error_msg = str(e)
        if "任务不存在" in error_msg:
            logger.warning(f"API 响应 - 任务不存在: task_id={task_id}")
            raise HTTPException(status_code=404, detail=error_msg)
        else:
            logger.warning(f"API 响应 - 启动任务失败: {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API 错误 - 启动修补任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="启动修补任务失败")


@router.get("/tasks/{task_id}/status", response_model=ApiResponse)
async def get_task_status(
    task_id: str,
    repair_service: RepairService = Depends(get_repair_service),
):
    """
    获取任务处理状态（用于轮询）。

    `data` 与 `TaskSimple` 一致（名称、状态、prompt、计数、时间戳等），
    与列表项及创建/更新接口返回的摘要结构相同。
    不含 `error_message` 与图片 URL 列表；任务结束后请再调 `GET /tasks/{task_id}` 取详情与结果图。
    """
    logger.debug(f"API 请求 - 获取任务状态: task_id={task_id}")

    try:
        task = repair_service.get_task(task_id)

        if not task:
            logger.warning(f"API 响应 - 任务不存在: task_id={task_id}")
            raise HTTPException(status_code=404, detail="任务不存在")

        task_simple = repair_service.build_task_simple_response(task)

        logger.debug(
            f"API 响应 - 获取任务状态成功: task_id={task_id}, status={task.status}"
        )

        return ApiResponse(
            success=True,
            data=task_simple.model_dump(),
            message="获取任务状态成功"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API 错误 - 获取任务状态失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取任务状态失败")


logger.debug("修补模块路由加载完成")
