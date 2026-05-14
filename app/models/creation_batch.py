"""创作模块 — 首页批量自动化美图创作编排"""

import logging

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.database import Base

logger = logging.getLogger(__name__)


class CreationBatchRun(Base):
    """一次批量提交：多轮 Prompt 预生成 + 链式一键创作"""

    __tablename__ = "creation_batch_runs"

    id = Column(String, primary_key=True, index=True)
    status = Column(String(20), nullable=False, index=True, default="pending")
    iterations_total = Column(Integer, nullable=False)
    iterations_done = Column(Integer, nullable=False, default=0)
    config_json = Column(Text, nullable=False, default="{}")
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    items = relationship(
        "CreationBatchRunItem",
        back_populates="run",
        cascade="all, delete-orphan",
    )


class CreationBatchRunItem(Base):
    """单轮创作：一条种子 + 预生成任务 + 一键创作任务"""

    __tablename__ = "creation_batch_run_items"

    id = Column(String, primary_key=True, index=True)
    run_id = Column(
        String,
        ForeignKey("creation_batch_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_index = Column(Integer, nullable=False)
    character_id = Column(
        String,
        ForeignKey("material_characters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    seed_prompt_id = Column(String(128), nullable=False)
    seed_section = Column(String(32), nullable=False)
    seed_prompt_text = Column(Text, nullable=False)
    prompt_precreation_task_id = Column(String(64), nullable=True, index=True)
    quick_create_task_id = Column(String(64), nullable=True, index=True)
    status = Column(String(20), nullable=False, index=True, default="pending")
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    run = relationship("CreationBatchRun", back_populates="items")
