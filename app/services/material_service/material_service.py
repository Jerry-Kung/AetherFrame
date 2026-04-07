import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.models.material import MaterialCharacter
from app.repositories.material_repository import MaterialCharacterRepository
from app.services.material_service import material_file_service
from app.services.file_service import FileDeleteError, FileSaveError, FileValidationError

logger = logging.getLogger(__name__)

ALLOWED_SETTING_EXTENSIONS = {".txt", ".md"}


class MaterialService:
    """素材加工 — 角色业务逻辑"""

    def __init__(self, db: Session):
        self.db = db
        self.repo = MaterialCharacterRepository(db)

    def raw_image_url(self, character_id: str, stored_filename: str) -> str:
        return f"/api/material/characters/{character_id}/images/raw/{stored_filename}"

    def _maybe_promote_draft(self, char: MaterialCharacter) -> None:
        if char.status in ("processing", "done"):
            return
        has_setting = bool(char.setting_text and char.setting_text.strip())
        from app.models.material import MaterialCharacterRawImage

        n = self.db.query(MaterialCharacterRawImage).filter_by(character_id=char.id).count()
        if (has_setting or n > 0) and char.status == "idle":
            self.repo.update(char.id, {"status": "draft"})

    def create_character(self, name: str, display_name: Optional[str] = None) -> MaterialCharacter:
        data: Dict[str, Any] = {"name": name}
        if display_name is not None:
            data["display_name"] = display_name
        char = self.repo.create(data)
        material_file_service.ensure_character_dirs(char.id)
        return char

    def delete_character(self, character_id: str) -> bool:
        char = self.repo.get_by_id(character_id)
        if not char:
            return False
        if not self.repo.delete(character_id):
            return False
        material_file_service.delete_character_files(character_id)
        return True

    def get_character(self, character_id: str) -> Optional[MaterialCharacter]:
        return self.repo.get_by_id(character_id)

    def patch_character(
        self,
        character_id: str,
        name: Optional[str] = None,
        display_name: Optional[str] = None,
    ) -> MaterialCharacter:
        char = self.repo.get_by_id(character_id)
        if not char:
            raise ValueError("角色不存在")
        updates: Dict[str, Any] = {}
        if name is not None:
            updates["name"] = name.strip()
        if display_name is not None:
            updates["display_name"] = display_name.strip()
        if not updates:
            return char
        self.repo.update(character_id, updates)
        self.repo.touch_character_updated_at(character_id)
        return self.repo.get_by_id(character_id)

    def delete_raw_image(self, character_id: str, image_id: str) -> bool:
        char = self.repo.get_by_id(character_id)
        if not char:
            raise ValueError("角色不存在")
        stored = self.repo.delete_raw_image(character_id, image_id)
        if stored is None:
            return False
        material_file_service.delete_raw_image_file(character_id, stored)
        if char.avatar_filename == stored:
            self.repo.update(character_id, {"avatar_filename": None})
        char = self.repo.get_by_id(character_id)
        self._maybe_promote_draft(char)
        self.repo.touch_character_updated_at(character_id)
        return True

    def update_raw_image_tags(
        self, character_id: str, image_id: str, tags: List[str]
    ) -> bool:
        char = self.repo.get_by_id(character_id)
        if not char:
            raise ValueError("角色不存在")
        cleaned = [str(t).strip() for t in tags if str(t).strip()]
        if not cleaned:
            cleaned = ["其他"]
        row = self.repo.update_raw_image_tags(character_id, image_id, cleaned)
        if row is None:
            return False
        self.repo.touch_character_updated_at(character_id)
        return True

    def list_characters(self, skip: int = 0, limit: int = 100) -> Tuple[List[MaterialCharacter], int]:
        total = self.repo.count_all()
        items = self.repo.list_by_updated(skip=skip, limit=limit)
        return items, total

    def list_character_summaries(
        self, skip: int = 0, limit: int = 100
    ) -> Tuple[List[Dict[str, Any]], int]:
        from app.models.material import MaterialCharacterRawImage

        items, total = self.list_characters(skip=skip, limit=limit)
        summaries: List[Dict[str, Any]] = []
        for c in items:
            n = self.db.query(MaterialCharacterRawImage).filter_by(character_id=c.id).count()
            text = c.setting_text or ""
            first_img = (
                self.db.query(MaterialCharacterRawImage)
                .filter_by(character_id=c.id)
                .order_by(MaterialCharacterRawImage.created_at)
                .first()
            )
            avatar_url = ""
            if c.avatar_filename:
                avatar_url = self.raw_image_url(c.id, c.avatar_filename)
            elif first_img is not None:
                avatar_url = self.raw_image_url(c.id, first_img.stored_filename)
            summaries.append(
                {
                    "id": c.id,
                    "name": c.name,
                    "display_name": c.display_name or c.name,
                    "status": c.status,
                    "updated_at": c.updated_at,
                    "raw_image_count": n,
                    "setting_preview": text[:72] + ("…" if len(text) > 72 else ""),
                    "avatar_url": avatar_url,
                }
            )
        return summaries, total

    def update_setting_text(self, character_id: str, text: str) -> MaterialCharacter:
        char = self.repo.get_by_id(character_id)
        if not char:
            raise ValueError("角色不存在")
        self.repo.update(character_id, {"setting_text": text})
        char = self.repo.get_by_id(character_id)
        self._maybe_promote_draft(char)
        self.repo.touch_character_updated_at(character_id)
        return self.repo.get_by_id(character_id)

    def update_setting_from_upload(self, character_id: str, file: UploadFile) -> MaterialCharacter:
        char = self.repo.get_by_id(character_id)
        if not char:
            raise ValueError("角色不存在")
        fn = file.filename or ""
        ext = os.path.splitext(fn.lower())[1]
        if ext not in ALLOWED_SETTING_EXTENSIONS:
            raise FileValidationError(f"仅支持上传: {', '.join(sorted(ALLOWED_SETTING_EXTENSIONS))}")
        raw = file.file.read()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as e:
            raise FileValidationError("设定文件须为 UTF-8 编码") from e
        return self.update_setting_text(character_id, text)

    def upload_raw_images(
        self,
        character_id: str,
        files: List[UploadFile],
        tags_per_file: Optional[List[List[str]]] = None,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
        char = self.repo.get_by_id(character_id)
        if not char:
            raise ValueError("角色不存在")

        uploaded: List[Dict[str, Any]] = []
        failed: List[Dict[str, str]] = []

        if tags_per_file is None:
            tags_per_file = []
        for i, file in enumerate(files):
            tags = tags_per_file[i] if i < len(tags_per_file) else ["其他"]
            if not isinstance(tags, list):
                tags = ["其他"]
            tags = [str(t) for t in tags if str(t).strip()]
            if not tags:
                tags = ["其他"]

            image_id = material_file_service.new_image_id()
            try:
                stored = material_file_service.save_raw_image(character_id, image_id, file)
                self.repo.add_raw_image(character_id, image_id, stored, tags)
                uploaded.append(
                    {
                        "id": image_id,
                        "filename": stored,
                        "url": self.raw_image_url(character_id, stored),
                        "tags": tags,
                    }
                )
            except FileValidationError as e:
                failed.append(
                    {"original_filename": file.filename or "unknown", "error": str(e)}
                )
            except FileSaveError as e:
                failed.append(
                    {"original_filename": file.filename or "unknown", "error": str(e)}
                )
            except Exception as e:
                logger.error(f"参考图上传异常: {e}", exc_info=True)
                failed.append(
                    {"original_filename": file.filename or "unknown", "error": "上传失败"}
                )

        char = self.repo.get_by_id(character_id)
        self._maybe_promote_draft(char)
        self.repo.touch_character_updated_at(character_id)
        return uploaded, failed

    def get_raw_image_path(self, character_id: str, filename: str) -> Optional[str]:
        char = self.repo.get_by_id(character_id)
        if not char:
            return None
        row = self.repo.get_raw_image_by_filename(character_id, filename)
        if not row:
            return None
        return material_file_service.get_raw_image_path(character_id, filename)

    def character_to_detail_dict(self, char: MaterialCharacter) -> Dict[str, Any]:
        from app.models.material import MaterialCharacterRawImage

        rows = (
            self.db.query(MaterialCharacterRawImage)
            .filter_by(character_id=char.id)
            .order_by(MaterialCharacterRawImage.created_at)
            .all()
        )
        raw_images = []
        for r in rows:
            try:
                tags = json.loads(r.tags_json or "[]")
                if not isinstance(tags, list):
                    tags = []
            except json.JSONDecodeError:
                tags = []
            raw_images.append(
                {
                    "id": r.id,
                    "url": self.raw_image_url(char.id, r.stored_filename),
                    "tags": tags,
                }
            )
        try:
            official_photos = json.loads(char.official_photos_json or "[null,null,null]")
        except json.JSONDecodeError:
            official_photos = [None, None, None]
        try:
            bio = json.loads(char.bio_json or "{}")
            if not isinstance(bio, dict):
                bio = {}
        except json.JSONDecodeError:
            bio = {}

        avatar_url = ""
        if char.avatar_filename:
            avatar_url = self.raw_image_url(char.id, char.avatar_filename)

        return {
            "id": char.id,
            "name": char.name,
            "display_name": char.display_name or char.name,
            "avatar_url": avatar_url,
            "status": char.status,
            "updated_at": char.updated_at,
            "setting_text": char.setting_text or "",
            "raw_images": raw_images,
            "official_photos": official_photos,
            "bio": bio,
        }
