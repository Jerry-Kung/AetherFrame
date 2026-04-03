import logging
from sqlalchemy import Column, String, Integer, Text, DateTime, Boolean
from sqlalchemy.sql import func
from app.models.database import Base

logger = logging.getLogger(__name__)


class RepairTask(Base):
    """修补任务模型"""
    __tablename__ = "repair_tasks"

    id = Column(String, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    status = Column(String(20), nullable=False, index=True, default="pending")
    prompt = Column(Text, nullable=False)
    output_count = Column(Integer, nullable=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<RepairTask(id='{self.id}', name='{self.name}', status='{self.status}')>"


class PromptTemplate(Base):
    """Prompt 模板模型"""
    __tablename__ = "prompt_templates"

    id = Column(String, primary_key=True, index=True)
    label = Column(String(100), nullable=False)
    text = Column(Text, nullable=False)
    is_builtin = Column(Boolean, nullable=False, default=True, index=True)
    sort_order = Column(Integer, nullable=False, default=0, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<PromptTemplate(id='{self.id}', label='{self.label}', is_builtin={self.is_builtin})>"
