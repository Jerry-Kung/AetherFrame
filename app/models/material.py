import logging
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.database import Base

logger = logging.getLogger(__name__)


class MaterialCharacter(Base):
    """素材加工 — 角色主表"""

    __tablename__ = "material_characters"

    id = Column(String, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    display_name = Column(String(200), nullable=True)
    status = Column(String(20), nullable=False, index=True, default="idle")
    setting_text = Column(Text, nullable=False, default="")
    avatar_filename = Column(String(255), nullable=True)
    official_photos_json = Column(Text, nullable=False, default="[null,null,null,null,null]")
    bio_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    raw_images = relationship(
        "MaterialCharacterRawImage",
        back_populates="character",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<MaterialCharacter(id={self.id!r}, name={self.name!r}, status={self.status!r})>"


class MaterialCharacterRawImage(Base):
    """素材加工 — 角色原始参考图元数据"""

    __tablename__ = "material_character_raw_images"

    id = Column(String, primary_key=True, index=True)
    character_id = Column(
        String,
        ForeignKey("material_characters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stored_filename = Column(String(255), nullable=False)
    type = Column(String(20), nullable=False, index=True, default="official")
    tags_json = Column(Text, nullable=False, default="[]")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    character = relationship("MaterialCharacter", back_populates="raw_images")

    def __repr__(self):
        return f"<MaterialCharacterRawImage(id={self.id!r}, character_id={self.character_id!r})>"


class MaterialStandardPhotoTask(Base):
    """素材加工 — 标准照任务（每角色当前任务）"""

    __tablename__ = "material_standard_photo_tasks"

    id = Column(String, primary_key=True, index=True)
    character_id = Column(
        String,
        ForeignKey("material_characters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        unique=True,
    )
    shot_type = Column(String(20), nullable=False)
    aspect_ratio = Column(String(10), nullable=False, default="9:16")
    output_count = Column(Integer, nullable=False, default=2)
    status = Column(String(20), nullable=False, index=True, default="pending")
    error_message = Column(Text, nullable=True)
    selected_raw_image_ids_json = Column(Text, nullable=False, default="[]")
    result_images_json = Column(Text, nullable=False, default="[]")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    character = relationship("MaterialCharacter")

    def __repr__(self):
        return (
            f"<MaterialStandardPhotoTask(id={self.id!r}, character_id={self.character_id!r}, "
            f"status={self.status!r})>"
        )


class MaterialCharaProfileTask(Base):
    """素材加工 — 角色小档案生成任务（每角色当前任务）"""

    __tablename__ = "material_chara_profile_tasks"

    id = Column(String, primary_key=True, index=True)
    character_id = Column(
        String,
        ForeignKey("material_characters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        unique=True,
    )
    status = Column(String(20), nullable=False, index=True, default="pending")
    error_message = Column(Text, nullable=True)
    selected_fanart_ids_json = Column(Text, nullable=False, default="[]")
    current_step = Column(String(40), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    character = relationship("MaterialCharacter")

    def __repr__(self):
        return (
            f"<MaterialCharaProfileTask(id={self.id!r}, character_id={self.character_id!r}, "
            f"status={self.status!r})>"
        )
