"""
创作模块 API — Prompt 预生成
"""
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.routes.material import ensure_valid_character_id
from app.schemas.creation import (
    ApiResponse,
    PromptPrecreationStartRequest,
    PromptPrecreationStartResponse,
    PromptPrecreationStatusResponse,
    PromptCardItem,
)
from app.services.creation_service.prompt_precreation_service import PromptPrecreationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/creation", tags=["creation"])


def get_prompt_precreation_service(db: Session = Depends(get_db)) -> PromptPrecreationService:
    return PromptPrecreationService(db)


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
