"""创作模块 — 生产出图人工 feedback。

设计文档：docs/superpowers/specs/2026-07-08-production-feedback-entry-design.md
一行 = 一张图的已填 feedback；文本清空且未勾选时删行，表里只存「已填」记录。
"""

import logging

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from app.models.database import Base

logger = logging.getLogger(__name__)


class CreationImageFeedback(Base):
    __tablename__ = "creation_image_feedbacks"

    id = Column(String, primary_key=True, index=True)
    quick_create_task_id = Column(String(64), nullable=False, index=True)
    prompt_id = Column(String(128), nullable=False)
    image_index = Column(Integer, nullable=False)
    leg_foot_bad = Column(Boolean, nullable=False, default=False)
    feedback_text = Column(Text, nullable=False, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint(
            "quick_create_task_id",
            "prompt_id",
            "image_index",
            name="uq_creation_image_feedback_image",
        ),
    )

    def __repr__(self):
        return (
            f"<CreationImageFeedback(id={self.id!r}, task={self.quick_create_task_id!r}, "
            f"prompt={self.prompt_id!r}, index={self.image_index!r})>"
        )
