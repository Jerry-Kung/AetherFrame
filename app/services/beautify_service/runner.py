import logging
import os
import time
from typing import Callable
from urllib.parse import urlparse

import requests

from app.repositories.beautify_repository import BeautifyRepository
from app.repositories.creation_repository import CreationQuickCreateRepository
from app.repositories.repair_repository import RepairTaskRepository
from app.services.beautify_service.path_utils import (
    beautified_basename,
    resolve_beautified_absolute_path,
    resolve_quick_create_source_path,
    resolve_repair_source_path,
)
from app.tools.beautify.enhancer import EnhanceResult, ImageEnhancer, get_default_enhancer
from app.tools.beautify.storage import CloudStorageClient, get_default_client
from app.utils.beautify_timeout import (
    BEAUTIFY_POLL_INTERVAL_SECONDS,
    BEAUTIFY_TIMEOUT_ERROR_MESSAGE,
    BEAUTIFY_TIMEOUT_SECONDS,
)
from app.utils.image_resize import resize_to_max_bytes

logger = logging.getLogger(__name__)


def run_beautify_task_sync(
    task_id: str,
    session_factory,
    *,
    storage: CloudStorageClient | None = None,
    enhancer: ImageEnhancer | None = None,
) -> None:
    storage = storage or get_default_client()
    enhancer = enhancer or get_default_enhancer()
    db = session_factory()
    cloud_object_key: str | None = None
    try:
        repo = BeautifyRepository(db)
        task = repo.get_by_id(task_id)
        if not task:
            return

        repo.update(
            task_id,
            {"status": "processing", "error_message": None},
        )

        if task.source_kind == "quick_create":
            qrepo = CreationQuickCreateRepository(db)
            source_task = qrepo.get_by_id(task.source_task_id)
            if not source_task:
                raise FileNotFoundError("源任务不存在")
            local_source = resolve_quick_create_source_path(
                source_task.work_dir, task.source_image_path
            )
            work_dir = source_task.work_dir
        elif task.source_kind == "repair":
            rrepo = RepairTaskRepository(db)
            if not rrepo.get_by_id(task.source_task_id):
                raise FileNotFoundError("源任务不存在")
            local_source = resolve_repair_source_path(
                task.source_task_id, task.source_image_path
            )
            work_dir = None
        else:
            raise ValueError("source_kind 不合法")

        beautified_abs = resolve_beautified_absolute_path(
            source_kind=task.source_kind,
            source_task_id=task.source_task_id,
            source_image_path=task.source_image_path,
            work_dir=work_dir,
        )
        os.makedirs(os.path.dirname(beautified_abs), exist_ok=True)

        repo.update(task_id, {"current_step": "uploading"})
        cloud_object_key, signed_url = storage.upload_and_presign(local_source)
        repo.update(
            task_id,
            {
                "cloud_object_key": cloud_object_key,
                "current_step": "uploading",
            },
        )

        repo.update(task_id, {"current_step": "submitting"})
        external_id = enhancer.submit(signed_url)
        repo.update(
            task_id,
            {
                "external_task_id": external_id,
                "current_step": "submitting",
            },
        )

        repo.update(task_id, {"current_step": "polling"})
        result_url = _poll_until_done(
            enhancer, external_id, lambda step: repo.update(task_id, {"current_step": step})
        )

        repo.update(task_id, {"current_step": "downloading", "result_url": result_url})
        _download_result(result_url, beautified_abs)

        repo.update(task_id, {"current_step": "postprocessing"})
        resize_to_max_bytes(beautified_abs)

        repo.update(
            task_id,
            {
                "status": "completed",
                "current_step": None,
                "beautified_filename": beautified_basename(task.source_image_path),
                "cloud_presigned_url": None,
                "error_message": None,
            },
        )
        logger.info(
            "beautify completed task_id=%s source_kind=%s source_task_id=%s",
            task_id,
            task.source_kind,
            task.source_task_id,
        )
    except Exception as exc:
        db.rollback()
        db2 = session_factory()
        try:
            repo = BeautifyRepository(db2)
            row = repo.get_by_id(task_id)
            step = row.current_step if row else None
            repo.update(
                task_id,
                {
                    "status": "failed",
                    "error_message": str(exc)[:500],
                    "current_step": step,
                },
            )
        finally:
            db2.close()
        logger.exception(
            "beautify failed task_id=%s err=%s",
            task_id,
            exc,
        )
    finally:
        db.close()
        if cloud_object_key:
            try:
                storage.delete(cloud_object_key)
                logger.info("beautify cleanup: deleted TOS object %s", cloud_object_key)
            except Exception as cleanup_err:
                logger.warning(
                    "beautify cleanup failed: object_key=%s err=%s",
                    cloud_object_key,
                    cleanup_err,
                )


def _poll_until_done(
    enhancer: ImageEnhancer,
    external_id: str,
    on_step: Callable[[str], None],
) -> str:
    deadline = time.monotonic() + BEAUTIFY_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        on_step("polling")
        result: EnhanceResult = enhancer.poll(external_id)
        if result.status == "running":
            time.sleep(BEAUTIFY_POLL_INTERVAL_SECONDS)
            continue
        if result.status == "succeeded":
            if not result.result_url:
                raise RuntimeError("高清化成功但缺少 result_url")
            parsed = urlparse(result.result_url)
            if parsed.scheme != "https":
                raise ValueError("结果 URL 协议不合法")
            return result.result_url
        raise RuntimeError(result.error or "高清化任务失败")
    raise TimeoutError(BEAUTIFY_TIMEOUT_ERROR_MESSAGE)


def _download_result(result_url: str, dest_path: str) -> None:
    with requests.get(result_url, stream=True, timeout=60) as resp:
        if not resp.ok:
            body = (resp.text or "")[:500]
            raise RuntimeError(f"HTTP {resp.status_code}: {body}")
        with open(dest_path, "wb") as out:
            for chunk in resp.iter_content(chunk_size=65536):
                if chunk:
                    out.write(chunk)
