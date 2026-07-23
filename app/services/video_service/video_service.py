import asyncio
import logging
import os
import shutil
import uuid
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks
from PIL import Image
from sqlalchemy.orm import Session

from app.models.database import BackgroundSessionLocal
from app.repositories.creation_repository import CreationQuickCreateRepository
from app.repositories.video_repository import VideoRepository
from app.services import directory_service
from app.services.video_service.exceptions import VideoConflictError, VideoNotFoundError
from app.services.video_service.runner import run_video_task_sync
from app.tools.llm.seedance import pick_closest_ratio

logger = logging.getLogger(__name__)

_RUNNING_STATES = ("pending", "uploading", "generating", "downloading")


class VideoService:
    def __init__(self, db: Session, *, session_factory=BackgroundSessionLocal):
        self.db = db
        self.repo = VideoRepository(db)
        self.quick_repo = CreationQuickCreateRepository(db)
        self._session_factory = session_factory

    # ---------- import ----------
    def _new_task_id(self) -> str:
        return f"vid_{uuid.uuid4().hex[:12]}"

    def _recommended_ratio(self, image_path: str) -> str:
        try:
            with Image.open(image_path) as im:
                return pick_closest_ratio(im.width, im.height)
        except Exception:
            return "1:1"

    def import_from_quick_create(
        self, source_task_id: str, source_image_path: str, ref_prompt_text: Optional[str]
    ) -> Dict[str, Any]:
        source_task = self.quick_repo.get_by_id(source_task_id)
        if not source_task:
            raise VideoNotFoundError("源产线任务不存在")
        abs_src = os.path.join(source_task.work_dir, source_image_path)
        if not os.path.exists(abs_src):
            raise VideoNotFoundError("源图片不存在")

        task_id = self._new_task_id()
        task_dir = directory_service.get_video_task_dir(task_id)
        os.makedirs(task_dir, exist_ok=True)
        ext = os.path.splitext(abs_src)[1] or ".png"
        ref_path = os.path.join(task_dir, f"ref{ext}")
        shutil.copyfile(abs_src, ref_path)

        ratio = self._recommended_ratio(ref_path)
        task = self.repo.create({
            "id": task_id, "source_kind": "quick_create",
            "source_task_id": source_task_id, "source_image_path": source_image_path,
            "ref_image_path": ref_path, "ref_prompt_text": ref_prompt_text,
            "image_role": "first_frame", "duration": 8, "generate_audio": False,
            "ratio": ratio, "status": "draft",
        })
        data = self.to_data(task)
        data["recommended_ratio"] = ratio
        return data

    def import_from_upload(self, filename: str, content: bytes) -> Dict[str, Any]:
        task_id = self._new_task_id()
        task_dir = directory_service.get_video_task_dir(task_id)
        os.makedirs(task_dir, exist_ok=True)
        ext = os.path.splitext(filename)[1].lower() or ".png"
        if ext not in (".png", ".jpg", ".jpeg", ".webp"):
            raise ValueError("仅支持 png/jpg/jpeg/webp 图片")
        ref_path = os.path.join(task_dir, f"ref{ext}")
        with open(ref_path, "wb") as f:
            f.write(content)

        ratio = self._recommended_ratio(ref_path)
        task = self.repo.create({
            "id": task_id, "source_kind": "upload",
            "ref_image_path": ref_path, "image_role": "first_frame",
            "duration": 8, "generate_audio": False, "ratio": ratio, "status": "draft",
        })
        data = self.to_data(task)
        data["recommended_ratio"] = ratio
        return data

    # ---------- submit ----------
    def submit(
        self,
        task_id: str,
        *,
        video_prompt_text: str,
        image_role: str,
        duration: int,
        generate_audio: bool,
        ratio: str,
        prompt_mode: str,
        background_tasks: Optional[BackgroundTasks] = None,
    ) -> Dict[str, Any]:
        task = self.repo.get_by_id(task_id)
        if not task:
            raise VideoNotFoundError("视频任务不存在")
        if task.status in _RUNNING_STATES:
            raise VideoConflictError("该任务已在生成中")
        if task.status == "completed":
            raise VideoConflictError("该任务已完成，请重新导入以创作新视频")

        inflight = self.repo.get_inflight()
        if inflight and inflight.id != task_id:
            raise VideoConflictError("已有视频任务进行中，请等待其完成")

        self.repo.update(task_id, {
            "video_prompt_text": video_prompt_text, "image_role": image_role,
            "duration": duration, "generate_audio": generate_audio, "ratio": ratio,
            "prompt_mode": prompt_mode, "status": "pending", "error_message": None,
        })
        if background_tasks:
            background_tasks.add_task(self._run_async, task_id)
        else:
            run_video_task_sync(task_id, self._session_factory)
        return self.get_status(task_id)

    async def _run_async(self, task_id: str) -> None:
        await asyncio.to_thread(run_video_task_sync, task_id, self._session_factory)

    # ---------- query / delete ----------
    def get_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        task = self.repo.get_by_id(task_id)
        return self.to_data(task) if task else None

    def list_tasks(self) -> List[Dict[str, Any]]:
        return [self.to_data(t) for t in self.repo.list_all(limit=200)]

    def delete_task(self, task_id: str) -> None:
        task = self.repo.get_by_id(task_id)
        if not task:
            raise VideoNotFoundError("视频任务不存在")
        if task.status in _RUNNING_STATES:
            raise VideoConflictError("任务生成中，无法删除")
        task_dir = directory_service.get_video_task_dir(task_id)
        if os.path.isdir(task_dir):
            shutil.rmtree(task_dir, ignore_errors=True)
        self.repo.delete(task_id)

    def to_data(self, task) -> Dict[str, Any]:
        return {
            "task_id": task.id, "source_kind": task.source_kind, "status": task.status,
            "image_role": task.image_role, "duration": task.duration,
            "generate_audio": task.generate_audio, "ratio": task.ratio,
            "ref_prompt_text": task.ref_prompt_text, "video_prompt_text": task.video_prompt_text,
            "prompt_mode": task.prompt_mode, "prompt_job_status": task.prompt_job_status,
            "prompt_job_result": task.prompt_job_result, "prompt_job_error": task.prompt_job_error,
            "video_filename": task.video_filename, "error_message": task.error_message,
            "created_at": task.created_at, "updated_at": task.updated_at,
        }
