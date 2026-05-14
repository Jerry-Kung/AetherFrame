"""
创作模块 API — Prompt 预生成
"""
import logging
import os
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.routes.material import ensure_valid_character_id
from app.schemas.creation import (
    ApiResponse,
    BatchAutomationItemListResponse,
    BatchAutomationRunDetailResponse,
    BatchAutomationStartRequest,
    BatchAutomationStartResponse,
    QuickCreateStartRequest,
    QuickCreateStartResponse,
    QuickCreateStatusResponse,
    QuickCreatePromptResultItem,
    QuickCreateHistoryItem,
    QuickCreateHistoryDetailResponse,
    QuickCreateHistoryListResponse,
    QuickCreatePromptInput,
    PromptPrecreationStartRequest,
    PromptPrecreationStartResponse,
    PromptPrecreationStatusResponse,
    PromptPrecreationHistoryItem,
    PromptPrecreationHistoryDetailResponse,
    PromptPrecreationHistoryListResponse,
    PromptCardItem,
)
from app.services.creation_service.batch_automation_service import (
    BatchAutomationService,
    run_batch_automation_job,
)
from app.services.creation_service.prompt_precreation_service import PromptPrecreationService
from app.services.creation_service.quick_create_service import QuickCreateService

logger = logging.getLogger(__name__)

_PROMPT_PRECREATION_STATUSES = frozenset({"pending", "running", "completed", "failed"})

router = APIRouter(prefix="/api/creation", tags=["creation"])


def get_prompt_precreation_service(db: Session = Depends(get_db)) -> PromptPrecreationService:
    return PromptPrecreationService(db)


def get_quick_create_service(db: Session = Depends(get_db)) -> QuickCreateService:
    return QuickCreateService(db)


def get_batch_automation_service(db: Session = Depends(get_db)) -> BatchAutomationService:
    return BatchAutomationService(db)


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
        "API 请求 - 启动 Prompt 预生成: character_id=%s count=%s chain=%s",
        character_id,
        body.count,
        body.chain_quick_create is not None,
    )
    try:
        chain_payload = (
            body.chain_quick_create.model_dump(mode="json")
            if body.chain_quick_create
            else None
        )
        data = service.start_prompt_precreation(
            character_id=character_id,
            seed_prompt=body.seed_prompt,
            count=body.count,
            background_tasks=background_tasks,
            chain_quick_create=chain_payload,
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
        chained_quick_create_task_id=raw.get("chained_quick_create_task_id"),
        chain_error=raw.get("chain_error"),
    )
    return ApiResponse(
        success=True,
        data=payload.model_dump(mode="json"),
        message="获取任务状态成功",
    )


@router.get(
    "/prompt-precreation/history",
    response_model=ApiResponse,
)
async def list_prompt_precreation_history(
    limit: int = 50,
    offset: int = 0,
    status: Optional[str] = Query(
        None, description="可选：pending / running / completed / failed，仅返回该状态的任务"
    ),
    service: PromptPrecreationService = Depends(get_prompt_precreation_service),
):
    st = (status or "").strip()
    if st and st not in _PROMPT_PRECREATION_STATUSES:
        raise HTTPException(
            status_code=400,
            detail="status 必须为 pending、running、completed 或 failed",
        )
    data = service.list_history(limit=limit, offset=offset, status=st or None)
    payload = PromptPrecreationHistoryListResponse(
        items=[PromptPrecreationHistoryItem(**x) for x in data.get("items", [])],
        total=data.get("total", 0),
    )
    return ApiResponse(
        success=True,
        data=payload.model_dump(mode="json"),
        message="获取历史记录成功",
    )


@router.get(
    "/prompt-precreation/history/latest",
    response_model=ApiResponse,
)
async def get_latest_prompt_precreation_history(
    service: PromptPrecreationService = Depends(get_prompt_precreation_service),
):
    raw = service.get_latest_history()
    if not raw:
        return ApiResponse(success=True, data=None, message="暂无历史记录")
    payload = PromptPrecreationHistoryDetailResponse(
        **{
            **raw,
            "cards": [PromptCardItem(**x) for x in raw.get("cards", [])],
        }
    )
    return ApiResponse(
        success=True,
        data=payload.model_dump(mode="json"),
        message="获取最新历史记录成功",
    )


@router.get(
    "/prompt-precreation/history/latest-completed",
    response_model=ApiResponse,
)
async def get_latest_completed_prompt_precreation_history(
    service: PromptPrecreationService = Depends(get_prompt_precreation_service),
):
    """一键创作默认灵感来源：全库最近一条已完成的 Prompt 预生成任务（含 cards）。"""
    raw = service.get_latest_completed_history()
    if not raw:
        return ApiResponse(success=True, data=None, message="暂无已完成的 Prompt 预生成任务")
    payload = PromptPrecreationHistoryDetailResponse(
        **{
            **raw,
            "cards": [PromptCardItem(**x) for x in raw.get("cards", [])],
        }
    )
    return ApiResponse(
        success=True,
        data=payload.model_dump(mode="json"),
        message="获取最新已完成 Prompt 预生成记录成功",
    )


@router.get(
    "/prompt-precreation/history/{history_id}",
    response_model=ApiResponse,
)
async def get_prompt_precreation_history_detail(
    history_id: str,
    service: PromptPrecreationService = Depends(get_prompt_precreation_service),
):
    hid = (history_id or "").strip()
    if not hid:
        raise HTTPException(status_code=400, detail="history_id 无效")
    raw = service.get_history_detail(hid)
    if not raw:
        raise HTTPException(status_code=404, detail="历史记录不存在")
    payload = PromptPrecreationHistoryDetailResponse(
        **{
            **raw,
            "cards": [PromptCardItem(**x) for x in raw.get("cards", [])],
        }
    )
    return ApiResponse(
        success=True,
        data=payload.model_dump(mode="json"),
        message="获取历史详情成功",
    )


@router.delete(
    "/prompt-precreation/history/{history_id}",
    response_model=ApiResponse,
)
async def delete_prompt_precreation_history(
    history_id: str,
    service: PromptPrecreationService = Depends(get_prompt_precreation_service),
):
    hid = (history_id or "").strip()
    if not hid:
        raise HTTPException(status_code=400, detail="history_id 无效")
    try:
        data = service.delete_history(hid)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return ApiResponse(success=True, data=data, message="删除历史记录成功")


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
        seed_prompt=raw["seed_prompt"],
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


@router.get(
    "/quick-create/history",
    response_model=ApiResponse,
)
async def list_quick_create_history(
    limit: int = 50,
    offset: int = 0,
    service: QuickCreateService = Depends(get_quick_create_service),
):
    data = service.list_history(limit=limit, offset=offset)
    payload = QuickCreateHistoryListResponse(
        items=[QuickCreateHistoryItem(**x) for x in data.get("items", [])],
        total=data.get("total", 0),
    )
    return ApiResponse(success=True, data=payload.model_dump(mode="json"), message="获取历史记录成功")


@router.get(
    "/quick-create/history/latest",
    response_model=ApiResponse,
)
async def get_latest_quick_create_history(
    service: QuickCreateService = Depends(get_quick_create_service),
):
    raw = service.get_latest_history()
    if not raw:
        return ApiResponse(success=True, data=None, message="暂无历史记录")
    payload = QuickCreateHistoryDetailResponse(
        **{
            **raw,
            "selected_prompts": [QuickCreatePromptInput(**x) for x in raw.get("selected_prompts", [])],
            "results": [QuickCreatePromptResultItem(**x) for x in raw.get("results", [])],
        }
    )
    return ApiResponse(success=True, data=payload.model_dump(mode="json"), message="获取最新历史记录成功")


@router.get(
    "/quick-create/history/{history_id}",
    response_model=ApiResponse,
)
async def get_quick_create_history_detail(
    history_id: str,
    service: QuickCreateService = Depends(get_quick_create_service),
):
    hid = (history_id or "").strip()
    if not hid:
        raise HTTPException(status_code=400, detail="history_id 无效")
    raw = service.get_history_detail(hid)
    if not raw:
        raise HTTPException(status_code=404, detail="历史记录不存在")
    payload = QuickCreateHistoryDetailResponse(
        **{
            **raw,
            "selected_prompts": [QuickCreatePromptInput(**x) for x in raw.get("selected_prompts", [])],
            "results": [QuickCreatePromptResultItem(**x) for x in raw.get("results", [])],
        }
    )
    return ApiResponse(success=True, data=payload.model_dump(mode="json"), message="获取历史详情成功")


@router.delete(
    "/quick-create/history/{history_id}",
    response_model=ApiResponse,
)
async def delete_quick_create_history(
    history_id: str,
    service: QuickCreateService = Depends(get_quick_create_service),
):
    hid = (history_id or "").strip()
    if not hid:
        raise HTTPException(status_code=400, detail="history_id 无效")
    try:
        data = service.delete_history(hid)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return ApiResponse(success=True, data=data, message="删除历史记录成功")


@router.post(
    "/batch-automation/start",
    response_model=ApiResponse,
)
async def batch_automation_start(
    body: BatchAutomationStartRequest,
    background_tasks: BackgroundTasks,
    service: BatchAutomationService = Depends(get_batch_automation_service),
):
    logger.info(
        "API 请求 - 启动批量自动化创作: iterations=%s prompt_count=%s",
        body.iterations,
        body.prompt_count,
    )
    try:
        data = service.start_run(
            iterations=body.iterations,
            prompt_count=body.prompt_count,
            images_per_prompt=body.images_per_prompt,
            aspect_ratio=body.aspect_ratio,
            max_prompts=body.max_prompts,
            character_ids=body.character_ids,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error("API 错误 - 启动批量自动化创作失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="启动批量自动化创作失败") from e
    background_tasks.add_task(run_batch_automation_job, data["run_id"])
    return ApiResponse(
        success=True,
        data=BatchAutomationStartResponse(**data).model_dump(mode="json"),
        message="批量自动化创作任务已提交",
    )


@router.get(
    "/batch-automation/runs/{run_id}",
    response_model=ApiResponse,
)
async def batch_automation_get_run(
    run_id: str,
    service: BatchAutomationService = Depends(get_batch_automation_service),
):
    rid = (run_id or "").strip()
    if not rid:
        raise HTTPException(status_code=400, detail="run_id 无效")
    raw = service.get_run_payload(rid)
    if not raw:
        raise HTTPException(status_code=404, detail="批量创作任务不存在")
    payload = BatchAutomationRunDetailResponse(**jsonable_encoder(raw))
    return ApiResponse(
        success=True,
        data=payload.model_dump(mode="json"),
        message="获取批量创作任务成功",
    )


@router.get(
    "/batch-automation/items",
    response_model=ApiResponse,
)
async def batch_automation_list_items(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    service: BatchAutomationService = Depends(get_batch_automation_service),
):
    raw = service.list_items_page(limit=limit, offset=offset)
    payload = BatchAutomationItemListResponse(**jsonable_encoder(raw))
    return ApiResponse(
        success=True,
        data=payload.model_dump(mode="json"),
        message="获取批量创作条目成功",
    )


@router.delete(
    "/batch-automation/items/{item_id}",
    response_model=ApiResponse,
)
async def batch_automation_delete_item(
    item_id: str,
    service: BatchAutomationService = Depends(get_batch_automation_service),
):
    iid = (item_id or "").strip()
    if not iid:
        raise HTTPException(status_code=400, detail="item_id 无效")
    try:
        data = service.delete_batch_item(iid)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return ApiResponse(success=True, data=data, message="删除批量创作条目成功")


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
