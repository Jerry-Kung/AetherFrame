from sqlalchemy import Column, DateTime, Index, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from app.models.database import Base


class ImageBeautifyTask(Base):
    __tablename__ = "image_beautify_tasks"

    id = Column(String(40), primary_key=True)
    source_kind = Column(String(20), nullable=False)
    source_task_id = Column(String(64), nullable=False, index=True)
    source_image_path = Column(Text, nullable=False)

    beautified_filename = Column(String(255), nullable=True)

    status = Column(String(20), nullable=False, default="pending")
    current_step = Column(String(40), nullable=True)
    error_message = Column(Text, nullable=True)

    cloud_object_key = Column(Text, nullable=True)
    cloud_presigned_url = Column(Text, nullable=True)
    external_task_id = Column(String(128), nullable=True, index=True)
    result_url = Column(Text, nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "source_kind",
            "source_task_id",
            "source_image_path",
            name="uk_beautify_source",
        ),
        Index("ix_beautify_status_created", "status", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<ImageBeautifyTask(id={self.id!r}, source_kind={self.source_kind!r}, "
            f"status={self.status!r})>"
        )
