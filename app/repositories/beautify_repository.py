import logging
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.beautify import ImageBeautifyTask
from app.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class BeautifyRepository(BaseRepository[ImageBeautifyTask]):
    def __init__(self, db: Session):
        super().__init__(db, ImageBeautifyTask)

    def get_inflight(
        self,
        source_kind: str,
        source_task_id: str,
        source_image_path: str,
    ) -> Optional[ImageBeautifyTask]:
        return (
            self.db.query(ImageBeautifyTask)
            .filter(
                ImageBeautifyTask.source_kind == source_kind,
                ImageBeautifyTask.source_task_id == source_task_id,
                ImageBeautifyTask.source_image_path == source_image_path,
                ImageBeautifyTask.status.in_(("pending", "processing")),
            )
            .first()
        )

    def get_by_source(
        self,
        source_kind: str,
        source_task_id: str,
        source_image_path: str,
    ) -> Optional[ImageBeautifyTask]:
        return (
            self.db.query(ImageBeautifyTask)
            .filter(
                ImageBeautifyTask.source_kind == source_kind,
                ImageBeautifyTask.source_task_id == source_task_id,
                ImageBeautifyTask.source_image_path == source_image_path,
            )
            .first()
        )

    def list_by_source(
        self, source_kind: str, source_task_id: str
    ) -> List[ImageBeautifyTask]:
        return (
            self.db.query(ImageBeautifyTask)
            .filter(
                ImageBeautifyTask.source_kind == source_kind,
                ImageBeautifyTask.source_task_id == source_task_id,
            )
            .order_by(ImageBeautifyTask.created_at.desc())
            .all()
        )

    def list_by_sources(
        self, source_kind: str, source_task_ids: List[str]
    ) -> Dict[str, List[ImageBeautifyTask]]:
        """批量按 source_task_id 拉 beautify 行，返回 {source_task_id: [rows]}。

        每个分组内部按 created_at desc 排序，保持与 list_by_source 一致。
        """
        if not source_task_ids:
            return {}
        ids = list({tid for tid in source_task_ids if tid})
        if not ids:
            return {}
        rows = (
            self.db.query(ImageBeautifyTask)
            .filter(
                ImageBeautifyTask.source_kind == source_kind,
                ImageBeautifyTask.source_task_id.in_(ids),
            )
            .order_by(ImageBeautifyTask.created_at.desc())
            .all()
        )
        grouped: Dict[str, List[ImageBeautifyTask]] = {tid: [] for tid in ids}
        for row in rows:
            grouped.setdefault(row.source_task_id, []).append(row)
        return grouped

    def list_by_external_id(self, external_task_id: str) -> List[ImageBeautifyTask]:
        return (
            self.db.query(ImageBeautifyTask)
            .filter(ImageBeautifyTask.external_task_id == external_task_id)
            .all()
        )
