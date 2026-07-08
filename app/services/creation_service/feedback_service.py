"""生产出图人工 feedback：保存语义（清空即删）与全量导出聚合。

设计文档：docs/superpowers/specs/2026-07-08-production-feedback-entry-design.md §1/§2
"""

import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.creation_feedback import CreationImageFeedback
from app.repositories.creation_feedback_repository import CreationImageFeedbackRepository
from app.repositories.creation_repository import CreationQuickCreateRepository

logger = logging.getLogger(__name__)


def serialize_feedback_row(row: CreationImageFeedback) -> Dict[str, Any]:
    return {
        "prompt_id": row.prompt_id,
        "image_index": int(row.image_index),
        "leg_foot_bad": bool(row.leg_foot_bad),
        "feedback_text": row.feedback_text or "",
    }


class ImageFeedbackService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = CreationImageFeedbackRepository(db)
        self.quick_repo = CreationQuickCreateRepository(db)

    def save_feedback(
        self,
        *,
        task_id: str,
        prompt_id: str,
        image_index: int,
        feedback_text: str,
        leg_foot_bad: bool,
    ) -> Optional[Dict[str, Any]]:
        tid = (task_id or "").strip()
        pid = (prompt_id or "").strip()
        if not tid or not pid:
            raise ValueError("task_id / prompt_id 无效")
        if self.quick_repo.get_by_id(tid) is None:
            raise ValueError("一键创作任务不存在")

        text = (feedback_text or "").strip()
        bad = bool(leg_foot_bad)
        if not text and not bad:
            self.repo.delete_for_image(tid, pid, image_index)
            return None
        row = self.repo.upsert(
            quick_create_task_id=tid,
            prompt_id=pid,
            image_index=image_index,
            leg_foot_bad=bad,
            feedback_text=text,
        )
        return serialize_feedback_row(row)
