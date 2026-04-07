import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.material import (
    MaterialCharacter,
    MaterialCharacterRawImage,
    MaterialStandardPhotoTask,
)

logger = logging.getLogger(__name__)
SHOT_TYPE_TO_INDEX = {
    "full_front": 0,
    "full_side": 1,
    "half_front": 2,
    "half_side": 3,
    "face_close": 4,
}


def _normalize_official_photos(photos_json: str) -> List[Optional[str]]:
    try:
        photos = json.loads(photos_json or "[]")
    except json.JSONDecodeError:
        photos = []
    if not isinstance(photos, list):
        photos = []
    normalized: List[Optional[str]] = []
    for i in range(5):
        value = photos[i] if i < len(photos) else None
        normalized.append(value if isinstance(value, str) and value.strip() else None)
    return normalized


class MaterialCharacterRepository(BaseRepository[MaterialCharacter]):
    """素材加工 — 角色数据访问"""

    def __init__(self, db: Session):
        super().__init__(db, MaterialCharacter)

    def create(self, data: Dict) -> MaterialCharacter:
        data = data.copy()
        if "id" not in data:
            data["id"] = f"mchar_{uuid.uuid4().hex[:10]}"
        if "status" not in data:
            data["status"] = "idle"
        if "setting_text" not in data:
            data["setting_text"] = ""
        if "official_photos_json" not in data:
            data["official_photos_json"] = "[null,null,null,null,null]"
        if "bio_json" not in data:
            data["bio_json"] = "{}"
        if data.get("display_name") is None and data.get("name"):
            data["display_name"] = data["name"]
        return super().create(data)

    def list_by_updated(self, skip: int = 0, limit: int = 100) -> List[MaterialCharacter]:
        return (
            self.db.query(MaterialCharacter)
            .order_by(desc(MaterialCharacter.updated_at))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_all(self) -> int:
        return self.db.query(MaterialCharacter).count()

    def add_raw_image(
        self,
        character_id: str,
        image_id: str,
        stored_filename: str,
        image_type: str,
        tags: List[str],
    ) -> MaterialCharacterRawImage:
        row = MaterialCharacterRawImage(
            id=image_id,
            character_id=character_id,
            stored_filename=stored_filename,
            type=image_type,
            tags_json=json.dumps(tags, ensure_ascii=False),
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        logger.info(f"添加原始参考图记录: {image_id} -> {character_id}")
        return row

    def get_raw_image(self, character_id: str, image_id: str) -> Optional[MaterialCharacterRawImage]:
        return (
            self.db.query(MaterialCharacterRawImage)
            .filter(
                MaterialCharacterRawImage.character_id == character_id,
                MaterialCharacterRawImage.id == image_id,
            )
            .first()
        )

    def get_raw_image_by_filename(
        self, character_id: str, filename: str
    ) -> Optional[MaterialCharacterRawImage]:
        return (
            self.db.query(MaterialCharacterRawImage)
            .filter(
                MaterialCharacterRawImage.character_id == character_id,
                MaterialCharacterRawImage.stored_filename == filename,
            )
            .first()
        )

    def list_raw_images(self, character_id: str) -> List[MaterialCharacterRawImage]:
        return (
            self.db.query(MaterialCharacterRawImage)
            .filter(MaterialCharacterRawImage.character_id == character_id)
            .order_by(MaterialCharacterRawImage.created_at)
            .all()
        )

    def delete_raw_image(self, character_id: str, image_id: str) -> Optional[str]:
        row = self.get_raw_image(character_id, image_id)
        if not row:
            return None
        fn = row.stored_filename
        self.db.delete(row)
        self.db.commit()
        logger.info(f"删除原始参考图记录: {image_id}")
        return fn

    def update_raw_image_tags(
        self, character_id: str, image_id: str, tags: List[str]
    ) -> Optional[MaterialCharacterRawImage]:
        row = self.get_raw_image(character_id, image_id)
        if not row:
            return None
        row.tags_json = json.dumps(tags, ensure_ascii=False)
        self.db.commit()
        self.db.refresh(row)
        return row

    def touch_character_updated_at(self, character_id: str) -> None:
        char = self.get_by_id(character_id)
        if not char:
            return
        char.updated_at = datetime.now(timezone.utc)
        self.db.add(char)
        self.db.commit()
        self.db.refresh(char)

    def get_standard_photo_task_by_character_id(
        self, character_id: str
    ) -> Optional[MaterialStandardPhotoTask]:
        return (
            self.db.query(MaterialStandardPhotoTask)
            .filter(MaterialStandardPhotoTask.character_id == character_id)
            .first()
        )

    def upsert_standard_photo_task(
        self,
        character_id: str,
        shot_type: str,
        aspect_ratio: str,
        output_count: int,
        selected_raw_image_ids: List[str],
        status: str = "pending",
        error_message: Optional[str] = None,
        result_images: Optional[List[str]] = None,
    ) -> MaterialStandardPhotoTask:
        task = self.get_standard_photo_task_by_character_id(character_id)
        if task is None:
            task = MaterialStandardPhotoTask(
                id=f"mphoto_{uuid.uuid4().hex[:10]}",
                character_id=character_id,
                shot_type=shot_type,
                aspect_ratio=aspect_ratio,
                output_count=output_count,
                status=status,
                error_message=error_message,
                selected_raw_image_ids_json=json.dumps(selected_raw_image_ids, ensure_ascii=False),
                result_images_json=json.dumps(result_images or [], ensure_ascii=False),
            )
            self.db.add(task)
        else:
            task.shot_type = shot_type
            task.aspect_ratio = aspect_ratio
            task.output_count = output_count
            task.status = status
            task.error_message = error_message
            task.selected_raw_image_ids_json = json.dumps(selected_raw_image_ids, ensure_ascii=False)
            task.result_images_json = json.dumps(result_images or [], ensure_ascii=False)
        self.db.commit()
        self.db.refresh(task)
        return task

    def update_standard_photo_task(
        self,
        task_id: str,
        updates: Dict,
    ) -> Optional[MaterialStandardPhotoTask]:
        task = self.db.query(MaterialStandardPhotoTask).filter_by(id=task_id).first()
        if not task:
            return None
        for key, value in updates.items():
            if key.endswith("_json") and value is not None and not isinstance(value, str):
                value = json.dumps(value, ensure_ascii=False)
            if hasattr(task, key):
                setattr(task, key, value)
        self.db.commit()
        self.db.refresh(task)
        return task

    def save_official_photo_by_shot_type(
        self,
        character_id: str,
        shot_type: str,
        photo_url: str,
    ) -> Optional[MaterialCharacter]:
        char = self.get_by_id(character_id)
        if not char:
            return None
        idx = SHOT_TYPE_TO_INDEX.get(shot_type)
        if idx is None:
            raise ValueError(f"不支持的标准照类型: {shot_type}")
        photos = _normalize_official_photos(char.official_photos_json)
        photos[idx] = photo_url
        char.official_photos_json = json.dumps(photos, ensure_ascii=False)
        char.updated_at = datetime.now(timezone.utc)
        self.db.add(char)
        self.db.commit()
        self.db.refresh(char)
        return char
