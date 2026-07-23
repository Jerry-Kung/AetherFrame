"""
应用启动时：将仍处于进行中的图片生成类任务标记为 failed（进程重启后后台任务已丢失）。
"""

from __future__ import annotations

import logging
import os
from typing import Dict

from app.models.beautify import ImageBeautifyTask
from app.models.creation import CreationQuickCreateTask
from app.models.material import MaterialStandardPhotoTask
from app.models.repair import RepairTask
from app.models.video import VideoCreationTask
from app.models.database import SessionLocal
from app.repositories.beautify_repository import BeautifyRepository
from app.repositories.creation_repository import CreationQuickCreateRepository
from app.repositories.material_repository import MaterialCharacterRepository
from app.repositories.repair_repository import RepairTaskRepository
from app.repositories.video_repository import VideoRepository
from app.utils.beautify_timeout import BEAUTIFY_RESTART_ERROR_MESSAGE
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
        return {"standard_photo": 0, "quick_create": 0, "repair": 0, "beautify": 0, "video": 0}

    counts = {"standard_photo": 0, "quick_create": 0, "repair": 0, "beautify": 0, "video": 0}
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

        brepo = BeautifyRepository(db)
        beautify_tasks = (
            db.query(ImageBeautifyTask)
            .filter(ImageBeautifyTask.status.in_(("pending", "processing")))
            .all()
        )
        for t in beautify_tasks:
            updated = brepo.update(
                t.id,
                {
                    "status": "failed",
                    "error_message": BEAUTIFY_RESTART_ERROR_MESSAGE,
                    "current_step": None,
                },
            )
            if updated:
                counts["beautify"] += 1

        vrepo = VideoRepository(db)
        video_tasks = (
            db.query(VideoCreationTask)
            .filter(VideoCreationTask.status.in_(
                ("pending", "uploading", "generating", "downloading")
            ))
            .all()
        )
        for t in video_tasks:
            updated = vrepo.update(
                t.id,
                {"status": "failed", "error_message": "服务重启，任务已中断，请重新提交"},
            )
            if updated:
                counts["video"] += 1

        logger.info(
            "启动时已将未完成图片生成任务标记为失败: standard_photo=%s quick_create=%s repair=%s beautify=%s video=%s",
            counts["standard_photo"],
            counts["quick_create"],
            counts["repair"],
            counts["beautify"],
            counts["video"],
        )
        return counts
    finally:
        db.close()
