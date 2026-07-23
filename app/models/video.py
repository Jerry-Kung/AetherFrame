from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String, Text
from sqlalchemy.sql import func

from app.models.database import Base


class VideoCreationTask(Base):
    __tablename__ = "video_creation_tasks"

    id = Column(String(40), primary_key=True)

    source_kind = Column(String(20), nullable=False)  # upload | quick_create
    source_task_id = Column(String(64), nullable=True, index=True)
    source_image_path = Column(Text, nullable=True)

    ref_image_path = Column(Text, nullable=False)
    ref_prompt_text = Column(Text, nullable=True)
    video_prompt_text = Column(Text, nullable=True)
    prompt_mode = Column(String(20), nullable=True)  # llm | manual

    image_role = Column(String(20), nullable=False, default="first_frame")
    duration = Column(Integer, nullable=False, default=8)
    generate_audio = Column(Boolean, nullable=False, default=False)
    ratio = Column(String(16), nullable=False, default="1:1")

    status = Column(String(20), nullable=False, default="draft", index=True)

    prompt_job_status = Column(String(20), nullable=True)  # pending|running|completed|failed
    prompt_job_result = Column(Text, nullable=True)
    prompt_job_error = Column(Text, nullable=True)

    seedance_task_id = Column(String(64), nullable=True, index=True)
    video_filename = Column(String(255), nullable=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_video_status_created", "status", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<VideoCreationTask(id={self.id!r}, status={self.status!r})>"
