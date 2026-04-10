"""
创作模块 API — Prompt 预生成
"""
import logging
import os

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.routes.material import ensure_valid_character_id
from app.schemas.creation import (
    ApiResponse,
    QuickCreateStartRequest,
    QuickCreateStartResponse,
    QuickCreateStatusResponse,
    QuickCreatePromptResultItem,
    PromptPrecreationStartRequest,
    PromptPrecreationStartResponse,
    PromptPrecreationStatusResponse,
    PromptCardItem,
)
from app.services.creation_service.prompt_precreation_service import PromptPrecreationService
from app.services.creation_service.quick_create_service import QuickCreateService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/creation", tags=["creation"])


def get_prompt_precreation_service(db: Session = Depends(get_db)) -> PromptPrecreationService:
    return PromptPrecreationService(db)


def get_quick_create_service(db: Session = Depends(get_db)) -> QuickCreateService:
    return QuickCreateService(db)


@router.post(
    "/characters/{character_id}/prompt-precreation/start",
    response_model=ApiResponse,
)
async def start_prompt_precreation(
    character_id: str,
    body: PromptPrecreationStartRequest,
    background_tasks: BackgroundTasks,
    service: PromptPrecreationService = Depends(get_prompt_precreation_service),
):
    character_id = ensure_valid_character_id(character_id)
    logger.info(
        "API 请求 - 启动 Prompt 预生成: character_id=%s count=%s",
        character_id,
        body.count,
    )
    try:
        data = service.start_prompt_precreation(
            character_id=character_id,
            seed_prompt=body.seed_prompt,
            count=body.count,
            background_tasks=background_tasks,
        )
        return ApiResponse(
            success=True,
            data=PromptPrecreationStartResponse(**data).model_dump(mode="json"),
            message="Prompt 预生成任务已启动",
        )
    except ValueError as e:
        msg = str(e)
        if msg == "角色不存在":
            raise HTTPException(status_code=404, detail=msg) from e
        raise HTTPException(status_code=400, detail=msg) from e
    except Exception as e:
        logger.error("API 错误 - 启动 Prompt 预生成失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="启动 Prompt 预生成失败") from e


@router.get(
    "/prompt-precreation/tasks/{task_id}/status",
    response_model=ApiResponse,
)
async def get_prompt_precreation_status(
    task_id: str,
    service: PromptPrecreationService = Depends(get_prompt_precreation_service),
):
    tid = (task_id or "").strip()
    if not tid:
        raise HTTPException(status_code=400, detail="task_id 无效")
    raw = service.get_task_status(tid)
    if not raw:
        raise HTTPException(status_code=404, detail="任务不存在")
    cards = raw.get("cards")
    card_models = None
    if cards is not None:
        card_models = [PromptCardItem(**c) for c in cards]
    payload = PromptPrecreationStatusResponse(
        task_id=raw["task_id"],
        character_id=raw["character_id"],
        status=raw["status"],
        error_message=raw.get("error_message"),
        current_step=raw.get("current_step"),
        created_at=raw["created_at"],
        updated_at=raw["updated_at"],
        cards=card_models,
    )
    return ApiResponse(
        success=True,
        data=payload.model_dump(mode="json"),
        message="获取任务状态成功",
    )


@router.post(
    "/characters/{character_id}/quick-create/start",
    response_model=ApiResponse,
)
async def start_quick_create(
    character_id: str,
    body: QuickCreateStartRequest,
    background_tasks: BackgroundTasks,
    service: QuickCreateService = Depends(get_quick_create_service),
):
    character_id = ensure_valid_character_id(character_id)
    logger.info(
        "API 请求 - 启动一键创作: character_id=%s prompts=%s n=%s aspect_ratio=%s",
        character_id,
        len(body.selected_prompts),
        body.n,
        body.aspect_ratio,
    )
    try:
        selected = [{"id": p.id, "fullPrompt": p.fullPrompt} for p in body.selected_prompts]
        data = service.start_quick_create(
            character_id=character_id,
            selected_prompts=selected,
            n=body.n,
            aspect_ratio=body.aspect_ratio,
            background_tasks=background_tasks,
        )
        return ApiResponse(
            success=True,
            data=QuickCreateStartResponse(**data).model_dump(mode="json"),
            message="一键创作任务已启动",
        )
    except ValueError as e:
        msg = str(e)
        if msg == "角色不存在":
            raise HTTPException(status_code=404, detail=msg) from e
        raise HTTPException(status_code=400, detail=msg) from e
    except Exception as e:
        logger.error("API 错误 - 启动一键创作失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="启动一键创作失败") from e


@router.get(
    "/quick-create/tasks/{task_id}/status",
    response_model=ApiResponse,
)
async def get_quick_create_status(
    task_id: str,
    service: QuickCreateService = Depends(get_quick_create_service),
):
    tid = (task_id or "").strip()
    if not tid:
        raise HTTPException(status_code=400, detail="task_id 无效")
    raw = service.get_task_status(tid)
    if not raw:
        raise HTTPException(status_code=404, detail="任务不存在")
    results = raw.get("results")
    result_models = None
    if results is not None:
        result_models = [QuickCreatePromptResultItem(**x) for x in results]
    payload = QuickCreateStatusResponse(
        task_id=raw["task_id"],
        character_id=raw["character_id"],
        status=raw["status"],
        error_message=raw.get("error_message"),
        current_step=raw.get("current_step"),
        n=raw["n"],
        aspect_ratio=raw["aspect_ratio"],
        created_at=raw["created_at"],
        updated_at=raw["updated_at"],
        results=result_models,
    )
    return ApiResponse(
        success=True,
        data=payload.model_dump(mode="json"),
        message="获取任务状态成功",
    )


@router.get("/quick-create/tasks/{task_id}/images/{image_path:path}")
async def get_quick_create_image(
    task_id: str,
    image_path: str,
    service: QuickCreateService = Depends(get_quick_create_service),
):
    tid = (task_id or "").strip()
    if not tid:
        raise HTTPException(status_code=400, detail="task_id 无效")
    path = service.get_task_image_path(tid, image_path)
    if not path:
        raise HTTPException(status_code=404, detail="文件不存在")
    ext = os.path.splitext(path)[1].lower()
    media_type = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(ext, "application/octet-stream")
    return FileResponse(path=path, media_type=media_type, filename=os.path.basename(path))
