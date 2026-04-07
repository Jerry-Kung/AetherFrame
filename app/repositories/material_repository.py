import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.material import MaterialCharacter, MaterialCharacterRawImage

logger = logging.getLogger(__name__)


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
            data["official_photos_json"] = "[null,null,null]"
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
        tags: List[str],
    ) -> MaterialCharacterRawImage:
        row = MaterialCharacterRawImage(
            id=image_id,
            character_id=character_id,
            stored_filename=stored_filename,
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
