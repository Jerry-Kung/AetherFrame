import logging
import uuid
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.creation_feedback import CreationImageFeedback

logger = logging.getLogger(__name__)


class CreationImageFeedbackRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_for_image(
        self, quick_create_task_id: str, prompt_id: str, image_index: int
    ) -> Optional[CreationImageFeedback]:
        return (
            self.db.query(CreationImageFeedback)
            .filter(
                CreationImageFeedback.quick_create_task_id == quick_create_task_id,
                CreationImageFeedback.prompt_id == prompt_id,
                CreationImageFeedback.image_index == image_index,
            )
            .first()
        )

    def upsert(
        self,
        *,
        quick_create_task_id: str,
        prompt_id: str,
        image_index: int,
        leg_foot_bad: bool,
        feedback_text: str,
    ) -> CreationImageFeedback:
        row = self.get_for_image(quick_create_task_id, prompt_id, image_index)
        if row is None:
            row = CreationImageFeedback(
                id=f"imgfb_{uuid.uuid4().hex[:12]}",
                quick_create_task_id=quick_create_task_id,
                prompt_id=prompt_id,
                image_index=image_index,
            )
            self.db.add(row)
        row.leg_foot_bad = bool(leg_foot_bad)
        row.feedback_text = feedback_text or ""
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_for_image(
        self, quick_create_task_id: str, prompt_id: str, image_index: int
    ) -> bool:
        row = self.get_for_image(quick_create_task_id, prompt_id, image_index)
        if row is None:
            return False
        self.db.delete(row)
        self.db.commit()
        return True

    def list_for_task_ids(
        self, task_ids: List[str]
    ) -> Dict[str, List[CreationImageFeedback]]:
        """按 quick_create_task_id 分组返回，仅含有已填记录的任务。"""
        if not task_ids:
            return {}
        rows = (
            self.db.query(CreationImageFeedback)
            .filter(CreationImageFeedback.quick_create_task_id.in_(list(set(task_ids))))
            .order_by(
                CreationImageFeedback.quick_create_task_id,
                CreationImageFeedback.prompt_id,
                CreationImageFeedback.image_index,
            )
            .all()
        )
        out: Dict[str, List[CreationImageFeedback]] = {}
        for r in rows:
            out.setdefault(r.quick_create_task_id, []).append(r)
        return out

    def list_all(self) -> List[CreationImageFeedback]:
        return (
            self.db.query(CreationImageFeedback)
            .order_by(
                CreationImageFeedback.quick_create_task_id,
                CreationImageFeedback.prompt_id,
                CreationImageFeedback.image_index,
            )
            .all()
        )

    def delete_for_task(self, quick_create_task_id: str) -> int:
        n = (
            self.db.query(CreationImageFeedback)
            .filter(CreationImageFeedback.quick_create_task_id == quick_create_task_id)
            .delete()
        )
        self.db.commit()
        return int(n)
