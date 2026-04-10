import logging

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.database import Base

logger = logging.getLogger(__name__)


class CreationPromptPrecreationTask(Base):
    """创作模块 — Prompt 预生成异步任务"""

    __tablename__ = "creation_prompt_precreation_tasks"

    id = Column(String, primary_key=True, index=True)
    character_id = Column(
        String,
        ForeignKey("material_characters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = Column(String(20), nullable=False, index=True, default="pending")
    error_message = Column(Text, nullable=True)
    seed_prompt = Column(Text, nullable=False)
    n = Column(Integer, nullable=False)
    work_dir = Column(Text, nullable=False)
    result_json = Column(Text, nullable=True)
    current_step = Column(String(40), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    character = relationship("MaterialCharacter")

    def __repr__(self):
        return (
            f"<CreationPromptPrecreationTask(id={self.id!r}, character_id={self.character_id!r}, "
            f"status={self.status!r})>"
        )
