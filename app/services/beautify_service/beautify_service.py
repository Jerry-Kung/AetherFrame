import asyncio
import logging
import os
import uuid
from typing import Any, Dict, Optional

from fastapi import BackgroundTasks
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.database import BackgroundSessionLocal
from app.repositories.beautify_repository import BeautifyRepository
from app.repositories.creation_repository import CreationQuickCreateRepository
from app.repositories.repair_repository import RepairTaskRepository
from app.services.beautify_service.exceptions import (
    BeautifyConflictError,
    BeautifyError,
    BeautifyNotFoundError,
)
from app.services.beautify_service.path_utils import (
    beautified_relative_path,
    normalize_relative_path,
    resolve_beautified_absolute_path,
    resolve_quick_create_source_path,
    resolve_repair_source_path,
)
from app.services.beautify_service.runner import run_beautify_task_sync
from app.tools.beautify.enhancer import ImageEnhancer
from app.tools.beautify.storage import CloudStorageClient

logger = logging.getLogger(__name__)

VALID_SOURCE_KINDS = frozenset({"quick_create", "repair"})


class BeautifyService:
    def __init__(
        self,
        db: Session,
        *,
        session_factory=BackgroundSessionLocal,
        storage: CloudStorageClient | None = None,
        enhancer: ImageEnhancer | None = None,
    ):
        self.db = db
        self.repo = BeautifyRepository(db)
        self.quick_repo = CreationQuickCreateRepository(db)
        self.repair_repo = RepairTaskRepository(db)
        self._session_factory = session_factory
        self._storage = storage
        self._enhancer = enhancer

    def _validate_source(self, source_kind: str, source_task_id: str, source_image_path: str):
        if source_kind not in VALID_SOURCE_KINDS:
            raise ValueError("source_kind 不合法")
        rel = normalize_relative_path(source_image_path)
        if source_kind == "quick_create":
            task = self.quick_repo.get_by_id(source_task_id)
            if not task:
                raise FileNotFoundError("源任务不存在")
            resolve_quick_create_source_path(task.work_dir, rel)
            return task.work_dir
        task = self.repair_repo.get_by_id(source_task_id)
        if not task:
            raise FileNotFoundError("源任务不存在")
        resolve_repair_source_path(source_task_id, rel)
        return None

    def start(
        self,
        *,
        source_kind: str,
        source_task_id: str,
        source_image_path: str,
        background_tasks: Optional[BackgroundTasks] = None,
    ) -> Dict[str, Any]:
        work_dir = self._validate_source(source_kind, source_task_id, source_image_path)
        rel = normalize_relative_path(source_image_path)

        inflight = self.repo.get_inflight(source_kind, source_task_id, rel)
        if inflight:
            return self._start_payload(inflight)

        existing = self.repo.get_by_source(source_kind, source_task_id, rel)
        if existing:
            if existing.status == "completed":
                raise BeautifyConflictError("已存在美化结果，请先删除")
            if existing.status == "failed":
                self.delete_beautify_artifacts(existing)

        task_id = f"bty_{uuid.uuid4().hex[:12]}"
        try:
            task = self.repo.create(
                {
                    "id": task_id,
                    "source_kind": source_kind,
                    "source_task_id": source_task_id,
                    "source_image_path": rel,
                    "status": "pending",
                }
            )
        except IntegrityError:
            self.db.rollback()
            inflight = self.repo.get_inflight(source_kind, source_task_id, rel)
            if inflight:
                return self._start_payload(inflight)
            raise BeautifyConflictError("已有美化任务进行中") from None

        logger.info(
            "beautify start task_id=%s source_kind=%s source_task_id=%s path=%s",
            task.id,
            source_kind,
            source_task_id,
            rel,
        )

        if background_tasks:
            background_tasks.add_task(self._run_async, task.id)
        else:
            run_beautify_task_sync(
                task.id,
                self._session_factory,
                storage=self._storage,
                enhancer=self._enhancer,
            )

        latest = self.repo.get_by_id(task.id) or task
        return self._start_payload(latest)

    async def _run_async(self, task_id: str) -> None:
        await asyncio.to_thread(
            run_beautify_task_sync,
            task_id,
            self._session_factory,
            storage=self._storage,
            enhancer=self._enhancer,
        )

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        task = self.repo.get_by_id(task_id)
        if not task:
            return None
        return self._status_payload(task)

    def delete_task(self, task_id: str) -> str:
        task = self.repo.get_by_id(task_id)
        if not task:
            raise BeautifyNotFoundError("美化任务不存在")
        if task.status in ("pending", "processing"):
            raise BeautifyConflictError("美化任务进行中，无法删除")
        self.delete_beautify_artifacts(task)
        return task_id

    def delete_beautify_artifacts(self, task) -> None:
        if task.cloud_object_key and self._storage:
            try:
                self._storage.delete(task.cloud_object_key)
            except Exception as exc:
                logger.warning(
                    "beautify delete cloud object failed task_id=%s key=%s err=%s",
                    task.id,
                    task.cloud_object_key,
                    exc,
                )
        elif task.cloud_object_key:
            try:
                from app.tools.beautify.storage import get_default_client

                get_default_client().delete(task.cloud_object_key)
            except Exception as exc:
                logger.warning(
                    "beautify delete cloud object failed task_id=%s key=%s err=%s",
                    task.id,
                    task.cloud_object_key,
                    exc,
                )

        try:
            work_dir = None
            if task.source_kind == "quick_create":
                source_task = self.quick_repo.get_by_id(task.source_task_id)
                work_dir = source_task.work_dir if source_task else None
            if task.beautified_filename:
                abs_path = resolve_beautified_absolute_path(
                    source_kind=task.source_kind,
                    source_task_id=task.source_task_id,
                    source_image_path=task.source_image_path,
                    work_dir=work_dir,
                )
                if os.path.isfile(abs_path):
                    os.remove(abs_path)
        except Exception as exc:
            logger.warning(
                "beautify delete local file failed task_id=%s err=%s",
                task.id,
                exc,
            )

        self.repo.delete(task.id)

    def cleanup_for_quick_create_task(self, task_id: str) -> int:
        rows = self.repo.list_by_source("quick_create", task_id)
        count = 0
        for row in list(rows):
            self.delete_beautify_artifacts(row)
            count += 1
        return count

    def cleanup_for_repair_task(self, task_id: str) -> int:
        rows = self.repo.list_by_source("repair", task_id)
        count = 0
        for row in list(rows):
            self.delete_beautify_artifacts(row)
            count += 1
        return count

    def _start_payload(self, task) -> Dict[str, Any]:
        return {
            "task_id": task.id,
            "status": task.status,
            "source_kind": task.source_kind,
            "source_task_id": task.source_task_id,
            "source_image_path": task.source_image_path,
        }

    def _status_payload(self, task) -> Dict[str, Any]:
        beautified_url = None
        if task.status == "completed" and task.beautified_filename:
            if task.source_kind == "quick_create":
                rel = beautified_relative_path(task.source_image_path)
                beautified_url = (
                    f"/api/creation/quick-create/tasks/{task.source_task_id}/images/{rel}"
                )
            elif task.source_kind == "repair":
                beautified_url = (
                    f"/api/repair/tasks/{task.source_task_id}/images/result/"
                    f"{task.beautified_filename}"
                )
        return {
            "task_id": task.id,
            "source_kind": task.source_kind,
            "source_task_id": task.source_task_id,
            "source_image_path": task.source_image_path,
            "status": task.status,
            "current_step": task.current_step,
            "error_message": task.error_message,
            "beautified_filename": task.beautified_filename,
            "beautified_url": beautified_url,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
        }
