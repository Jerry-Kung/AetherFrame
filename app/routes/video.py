import os

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.schemas.video import (
    ApiResponse,
    PromptJobBody,
    VideoImportBody,
    VideoSubmitBody,
)
from app.services import directory_service
from app.services.video_service.exceptions import VideoConflictError, VideoNotFoundError
from app.services.video_service.prompt_service import VideoPromptService
from app.services.video_service.video_service import VideoService
from app.utils.thumbnails import get_or_create_thumbnail

router = APIRouter(prefix="/api/video", tags=["video"])


def _svc(db: Session) -> VideoService:
    return VideoService(db)


@router.post("/tasks/import", response_model=ApiResponse)
def import_task(body: VideoImportBody, db: Session = Depends(get_db)):
    try:
        data = _svc(db).import_from_quick_create(
            body.source_task_id, body.source_image_path, body.ref_prompt_text
        )
        return ApiResponse(success=True, data=data, message="已导入")
    except VideoNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/tasks/upload", response_model=ApiResponse)
def upload_task(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = file.file.read()
    try:
        data = _svc(db).import_from_upload(file.filename or "ref.png", content)
        return ApiResponse(success=True, data=data, message="已上传")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/tasks/{task_id}/prompt-job/start", response_model=ApiResponse)
def start_prompt_job(
    task_id: str, body: PromptJobBody, background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    try:
        data = VideoPromptService(db).start_job(
            task_id, body.mode, body.manual_prompt, background_tasks
        )
        return ApiResponse(success=True, data=data, message="Prompt 作业已启动")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/tasks/{task_id}/prompt-job/status", response_model=ApiResponse)
def prompt_job_status(task_id: str, db: Session = Depends(get_db)):
    data = _svc(db).get_status(task_id)
    if not data:
        raise HTTPException(status_code=404, detail="视频任务不存在")
    return ApiResponse(success=True, data=data, message="ok")


@router.post("/tasks/{task_id}/submit", response_model=ApiResponse)
def submit_task(
    task_id: str, body: VideoSubmitBody, background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    try:
        data = _svc(db).submit(
            task_id, video_prompt_text=body.video_prompt_text, image_role=body.image_role,
            duration=body.duration, generate_audio=body.generate_audio, ratio=body.ratio,
            prompt_mode="manual", background_tasks=background_tasks,
        )
        return ApiResponse(success=True, data=data, message="已提交生成")
    except VideoNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except VideoConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/tasks/{task_id}/status", response_model=ApiResponse)
def task_status(task_id: str, db: Session = Depends(get_db)):
    data = _svc(db).get_status(task_id)
    if not data:
        raise HTTPException(status_code=404, detail="视频任务不存在")
    return ApiResponse(success=True, data=data, message="ok")


@router.get("/tasks", response_model=ApiResponse)
def list_tasks(db: Session = Depends(get_db)):
    return ApiResponse(success=True, data=_svc(db).list_tasks(), message="ok")


@router.get("/tasks/{task_id}/video")
def get_video(task_id: str, db: Session = Depends(get_db)):
    task = _svc(db).repo.get_by_id(task_id)
    if not task or not task.video_filename:
        raise HTTPException(status_code=404, detail="视频不存在")
    path = os.path.join(directory_service.get_video_task_dir(task_id), task.video_filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="视频文件缺失")
    return FileResponse(path, media_type="video/mp4", filename=f"{task_id}.mp4")


@router.get("/tasks/{task_id}/image")
def get_image(task_id: str, db: Session = Depends(get_db)):
    task = _svc(db).repo.get_by_id(task_id)
    if not task or not task.ref_image_path or not os.path.exists(task.ref_image_path):
        raise HTTPException(status_code=404, detail="参考图不存在")
    thumb = get_or_create_thumbnail(task.ref_image_path)
    if thumb:
        return FileResponse(thumb)
    return FileResponse(task.ref_image_path)


@router.delete("/tasks/{task_id}", response_model=ApiResponse)
def delete_task(task_id: str, db: Session = Depends(get_db)):
    try:
        _svc(db).delete_task(task_id)
        return ApiResponse(success=True, data={"deleted_id": task_id}, message="已删除")
    except VideoNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except VideoConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
