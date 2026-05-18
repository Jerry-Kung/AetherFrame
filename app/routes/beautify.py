import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.schemas.beautify import ApiResponse, BeautifyDeleteData, BeautifyStartBody
from app.services.beautify_service import (
    BeautifyConflictError,
    BeautifyError,
    BeautifyNotFoundError,
    BeautifyService,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["beautify"])


@router.post("/start", response_model=ApiResponse)
def start_beautify(
    body: BeautifyStartBody,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    service = BeautifyService(db)
    try:
        data = service.start(
            source_kind=body.source_kind,
            source_task_id=body.source_task_id,
            source_image_path=body.source_image_path,
            background_tasks=background_tasks,
        )
        return ApiResponse(success=True, data=data, message="美化任务已启动")
    except BeautifyConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except BeautifyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("start beautify failed")
        raise HTTPException(status_code=500, detail="内部错误") from exc


@router.get("/tasks/{task_id}/status", response_model=ApiResponse)
def get_beautify_task_status(task_id: str, db: Session = Depends(get_db)):
    service = BeautifyService(db)
    data = service.get_task_status(task_id)
    if not data:
        raise HTTPException(status_code=404, detail="美化任务不存在")
    return ApiResponse(success=True, data=data, message="ok")


@router.delete("/tasks/{task_id}", response_model=ApiResponse)
def delete_beautify_task(task_id: str, db: Session = Depends(get_db)):
    service = BeautifyService(db)
    try:
        deleted_id = service.delete_task(task_id)
        return ApiResponse(
            success=True,
            data=BeautifyDeleteData(deleted_id=deleted_id).model_dump(),
            message="美化结果已删除",
        )
    except BeautifyNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BeautifyConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("delete beautify task failed")
        raise HTTPException(status_code=500, detail="内部错误") from exc
