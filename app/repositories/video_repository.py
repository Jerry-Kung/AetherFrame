import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models.video import VideoCreationTask
from app.repositories.base import BaseRepository

logger = logging.getLogger(__name__)

_INFLIGHT_STATES = ("pending", "uploading", "generating", "downloading")


class VideoRepository(BaseRepository[VideoCreationTask]):
    def __init__(self, db: Session):
        super().__init__(db, VideoCreationTask)

    def get_inflight(self) -> Optional[VideoCreationTask]:
        return (
            self.db.query(VideoCreationTask)
            .filter(VideoCreationTask.status.in_(_INFLIGHT_STATES))
            .order_by(VideoCreationTask.created_at.desc())
            .first()
        )
