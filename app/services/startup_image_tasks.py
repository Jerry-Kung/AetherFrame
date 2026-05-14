"""
应用启动时：将仍处于进行中的图片生成类任务标记为 failed（进程重启后后台任务已丢失）。
"""

from __future__ import annotations

import logging
import os
from typing import Dict

from app.models.creation import CreationQuickCreateTask
from app.models.material import MaterialStandardPhotoTask
from app.models.repair import RepairTask
from app.models.database import SessionLocal
from app.repositories.creation_repository import CreationQuickCreateRepository
from app.repositories.material_repository import MaterialCharacterRepository
from app.repositories.repair_repository import RepairTaskRepository
from app.services.creation_service.quick_create_service import (
    _sync_quick_create_history_files_for_task_id,
)
from app.utils.image_generation_timeout import IMAGE_GEN_RESTART_ERROR_MESSAGE

logger = logging.getLogger(__name__)


def run_fail_inflight_image_generation_tasks() -> Dict[str, int]:
    """
    扫描标准照、一键创作、修补三类未完成的图片任务并置为 failed。
    设置环境变量 SKIP_STARTUP_IMAGE_TASK_RESET=1（或 true/yes）可跳过。
    """
    raw = (os.getenv("SKIP_STARTUP_IMAGE_TASK_RESET") or "").strip().lower()
    if raw in ("1", "true", "yes", "on"):
        logger.info("跳过启动时图片任务失败化: SKIP_STARTUP_IMAGE_TASK_RESET 已设置")
        return {"standard_photo": 0, "quick_create": 0, "repair": 0}

    counts = {"standard_photo": 0, "quick_create": 0, "repair": 0}
    db = SessionLocal()
    try:
        std_tasks = (
            db.query(MaterialStandardPhotoTask)
            .filter(MaterialStandardPhotoTask.status.in_(("pending", "processing")))
            .all()
        )
        mrepo = MaterialCharacterRepository(db)
        for t in std_tasks:
            updated = mrepo.update_standard_photo_task(
                t.id,
                {
                    "status": "failed",
                    "error_message": IMAGE_GEN_RESTART_ERROR_MESSAGE,
                },
            )
            if updated:
                counts["standard_photo"] += 1

        qc_tasks = (
            db.query(CreationQuickCreateTask)
            .filter(CreationQuickCreateTask.status.in_(("pending", "running")))
            .all()
        )
        qrepo = CreationQuickCreateRepository(db)
        for t in qc_tasks:
            updated = qrepo.update(
                t.id,
                {
                    "status": "failed",
                    "error_message": IMAGE_GEN_RESTART_ERROR_MESSAGE,
                    "current_step": None,
                },
            )
            if updated:
                _sync_quick_create_history_files_for_task_id(db, t.id)
                counts["quick_create"] += 1

        repair_tasks = (
            db.query(RepairTask).filter(RepairTask.status == "processing").all()
        )
        rrepo = RepairTaskRepository(db)
        for t in repair_tasks:
            updated = rrepo.update_status(
                t.id, "failed", IMAGE_GEN_RESTART_ERROR_MESSAGE
            )
            if updated:
                counts["repair"] += 1

        logger.info(
            "启动时已将未完成图片生成任务标记为失败: standard_photo=%s quick_create=%s repair=%s",
            counts["standard_photo"],
            counts["quick_create"],
            counts["repair"],
        )
        return counts
    finally:
        db.close()
