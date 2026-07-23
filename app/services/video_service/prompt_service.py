import asyncio
import logging
import os
from typing import Any, Callable, Dict, Optional

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.models.database import BackgroundSessionLocal
from app.prompts.video.optimize import OPTIMIZE_PROMPT
from app.prompts.video.recommend import RECOMMEND_PROMPT
from app.repositories.video_repository import VideoRepository
from app.tools.llm.yibu_llm_infer import yibu_gemini_infer

logger = logging.getLogger(__name__)


class VideoPromptService:
    def __init__(self, db: Session, *, session_factory=BackgroundSessionLocal):
        self.db = db
        self.repo = VideoRepository(db)
        self._session_factory = session_factory

    def start_job(
        self,
        task_id: str,
        mode: str,
        manual_prompt: Optional[str],
        background_tasks: Optional[BackgroundTasks] = None,
    ) -> Dict[str, Any]:
        task = self.repo.get_by_id(task_id)
        if not task:
            raise FileNotFoundError("视频任务不存在")
        if task.prompt_job_status in ("pending", "running"):
            raise ValueError("已有 Prompt 作业进行中")
        if mode == "optimize" and not (manual_prompt and manual_prompt.strip()):
            raise ValueError("优化模式需要提供手写 Prompt")

        self.repo.update(
            task_id,
            {"prompt_job_status": "pending", "prompt_job_result": None, "prompt_job_error": None},
        )
        if background_tasks:
            background_tasks.add_task(self._run_async, task_id, mode, manual_prompt)
        else:
            self.run_prompt_job_sync(task_id, mode, manual_prompt, self._session_factory)
        return {"task_id": task_id, "prompt_job_status": "pending"}

    async def _run_async(self, task_id: str, mode: str, manual_prompt: Optional[str]) -> None:
        await asyncio.to_thread(
            self.run_prompt_job_sync, task_id, mode, manual_prompt, self._session_factory
        )

    def run_prompt_job_sync(
        self,
        task_id: str,
        mode: str,
        manual_prompt: Optional[str],
        session_factory,
        *,
        infer: Optional[Callable[..., str]] = None,
    ) -> None:
        infer = infer or yibu_gemini_infer
        db = session_factory()
        try:
            repo = VideoRepository(db)
            task = repo.get_by_id(task_id)
            if not task:
                return
            repo.update(task_id, {"prompt_job_status": "running"})

            if mode == "optimize":
                prompt = OPTIMIZE_PROMPT.format(manual_prompt=manual_prompt or "")
                image_path = None
            else:
                prompt = RECOMMEND_PROMPT.format(ref_prompt=task.ref_prompt_text or "（无）")
                image_path = (
                    [task.ref_image_path]
                    if task.ref_image_path and os.path.exists(task.ref_image_path)
                    else None
                )

            result = infer(prompt, image_path=image_path, thinking_level="high")
            repo.update(
                task_id,
                {"prompt_job_status": "completed", "prompt_job_result": (result or "").strip()},
            )
        except Exception as exc:
            db.rollback()
            db2 = session_factory()
            try:
                VideoRepository(db2).update(
                    task_id,
                    {"prompt_job_status": "failed", "prompt_job_error": str(exc)[:500]},
                )
            finally:
                db2.close()
            logger.exception("video prompt job failed task_id=%s", task_id)
        finally:
            db.close()
