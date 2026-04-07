import asyncio
import json
import logging
import os
import uuid
from typing import Any, Dict, List, Optional, Tuple

from fastapi import BackgroundTasks
from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.models.material import MaterialCharacter
from app.prompts.material.standard_photo import (
    face_close_prompt,
    full_front_prompt,
    full_side_prompt,
    half_front_prompt,
    half_side_prompt,
)
from app.repositories.material_repository import MaterialCharacterRepository
from app.services.material_service import material_file_service
from app.services.file_service import FileDeleteError, FileSaveError, FileValidationError
from app.services.material_service import standard_photo_generation_service

logger = logging.getLogger(__name__)

ALLOWED_SETTING_EXTENSIONS = {".txt", ".md"}
RAW_IMAGE_TYPES = {"official", "fanart"}
SHOT_TYPE_TO_PROMPT = {
    "full_front": full_front_prompt,
    "full_side": full_side_prompt,
    "half_front": half_front_prompt,
    "half_side": half_side_prompt,
    "face_close": face_close_prompt,
}


class MaterialService:
    """素材加工 — 角色业务逻辑"""

    def __init__(self, db: Session):
        self.db = db
        self.repo = MaterialCharacterRepository(db)

    def raw_image_url(self, character_id: str, stored_filename: str) -> str:
        return f"/api/material/characters/{character_id}/images/raw/{stored_filename}"

    def standard_photo_result_image_url(self, character_id: str, filename: str) -> str:
        return f"/api/material/characters/{character_id}/standard-photo/result-images/{filename}"

    @staticmethod
    def _normalize_official_photos(data: Any) -> List[Optional[str]]:
        photos = data if isinstance(data, list) else []
        normalized: List[Optional[str]] = []
        for i in range(5):
            value = photos[i] if i < len(photos) else None
            normalized.append(value if isinstance(value, str) and value.strip() else None)
        return normalized

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
        row = self.repo.get_raw_image(character_id, image_id)
        if row is None:
            return False
        stored = self.repo.delete_raw_image(character_id, image_id)
        material_file_service.delete_raw_image_file(character_id, stored, row.type)
        if char.avatar_filename == row.stored_filename:
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
        types_per_file: Optional[List[str]] = None,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
        char = self.repo.get_by_id(character_id)
        if not char:
            raise ValueError("角色不存在")

        uploaded: List[Dict[str, Any]] = []
        failed: List[Dict[str, str]] = []

        if tags_per_file is None:
            tags_per_file = []
        if types_per_file is None:
            types_per_file = []
        for i, file in enumerate(files):
            tags = tags_per_file[i] if i < len(tags_per_file) else ["其他"]
            if not isinstance(tags, list):
                tags = ["其他"]
            tags = [str(t) for t in tags if str(t).strip()]
            if not tags:
                tags = ["其他"]

            image_type = types_per_file[i] if i < len(types_per_file) else "official"
            if image_type not in RAW_IMAGE_TYPES:
                image_type = "official"

            image_id = material_file_service.new_image_id()
            try:
                stored = material_file_service.save_raw_image(character_id, image_id, file, image_type)
                self.repo.add_raw_image(character_id, image_id, stored, image_type, tags)
                uploaded.append(
                    {
                        "id": image_id,
                        "filename": stored,
                        "url": self.raw_image_url(character_id, stored),
                        "type": image_type,
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
        return material_file_service.get_raw_image_path(character_id, filename, row.type)

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
                    "type": r.type if r.type in RAW_IMAGE_TYPES else "official",
                    "tags": tags,
                }
            )
        try:
            official_photos = json.loads(char.official_photos_json or "[null,null,null]")
        except json.JSONDecodeError:
            official_photos = []
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
            "official_photos": self._normalize_official_photos(official_photos),
            "bio": bio,
        }

    def start_standard_photo_task(
        self,
        character_id: str,
        shot_type: str,
        aspect_ratio: str,
        output_count: int,
        selected_raw_image_ids: List[str],
        background_tasks: Optional[BackgroundTasks] = None,
    ) -> Dict[str, Any]:
        char = self.repo.get_by_id(character_id)
        if not char:
            raise ValueError("角色不存在")
        if shot_type not in SHOT_TYPE_TO_PROMPT:
            raise ValueError("不支持的标准照类型")
        if output_count <= 0:
            raise ValueError("输出数量必须大于 0")

        selected_rows = []
        for image_id in selected_raw_image_ids:
            row = self.repo.get_raw_image(character_id, image_id)
            if row:
                selected_rows.append(row)
        if not selected_rows:
            raise ValueError("请至少选择一张有效参考图")

        task = self.repo.upsert_standard_photo_task(
            character_id=character_id,
            shot_type=shot_type,
            aspect_ratio=aspect_ratio,
            output_count=output_count,
            selected_raw_image_ids=selected_raw_image_ids,
            status="processing",
            error_message=None,
            result_images=[],
        )
        material_file_service.clear_standard_photo_task_results(character_id, task.id)
        if background_tasks:
            background_tasks.add_task(
                self._run_standard_photo_task,
                character_id,
                task.id,
            )
        else:
            self._run_standard_photo_task_sync(character_id, task.id)

        return {
            "task_id": task.id,
            "status": task.status,
            "shot_type": task.shot_type,
            "aspect_ratio": task.aspect_ratio,
            "output_count": task.output_count,
        }

    async def _run_standard_photo_task(self, character_id: str, task_id: str) -> None:
        await asyncio.to_thread(self._run_standard_photo_task_sync, character_id, task_id)

    def _run_standard_photo_task_sync(self, character_id: str, task_id: str) -> None:
        bind = self.db.get_bind()
        db = Session(bind=bind, autocommit=False, autoflush=False)
        try:
            repo = MaterialCharacterRepository(db)
            task = repo.update_standard_photo_task(task_id, {})
            if not task:
                return
            rows = []
            selected_ids = json.loads(task.selected_raw_image_ids_json or "[]")
            if not isinstance(selected_ids, list):
                selected_ids = []
            for image_id in selected_ids:
                row = repo.get_raw_image(character_id, str(image_id))
                if row:
                    rows.append(row)
            if not rows:
                repo.update_standard_photo_task(
                    task_id, {"status": "failed", "error_message": "未找到可用参考图"}
                )
                return

            official_paths: List[str] = []
            fanart_paths: List[str] = []
            for row in rows:
                image_path = material_file_service.get_raw_image_path(
                    character_id, row.stored_filename, row.type
                )
                if not image_path:
                    continue
                if row.type == "fanart":
                    fanart_paths.append(image_path)
                else:
                    official_paths.append(image_path)
            if not official_paths and not fanart_paths:
                repo.update_standard_photo_task(
                    task_id, {"status": "failed", "error_message": "所选参考图文件不存在"}
                )
                return

            content = standard_photo_generation_service.build_standard_photo_content(
                task_prompt=SHOT_TYPE_TO_PROMPT[task.shot_type],
                official_image_paths=official_paths,
                fanart_image_paths=fanart_paths,
            )
            temp_paths: List[str] = []
            temp_dir: Optional[str] = None
            try:
                temp_paths, err, temp_dir = standard_photo_generation_service.generate_standard_photo_images(
                    task_id=task.id,
                    content=content,
                    output_count=task.output_count,
                    aspect_ratio=task.aspect_ratio,
                )
                if err:
                    repo.update_standard_photo_task(task_id, {"status": "failed", "error_message": err})
                    return
                if not temp_paths:
                    repo.update_standard_photo_task(
                        task_id, {"status": "failed", "error_message": "没有生成任何候选图"}
                    )
                    return
                result_files: List[str] = []
                for i, temp_path in enumerate(temp_paths):
                    with open(temp_path, "rb") as f:
                        image_data = f.read()
                    saved_name = material_file_service.save_standard_photo_result_bytes(
                        character_id=character_id, task_id=task.id, image_data=image_data, index=i
                    )
                    result_files.append(saved_name)
                if not result_files:
                    repo.update_standard_photo_task(
                        task_id, {"status": "failed", "error_message": "候选图保存失败"}
                    )
                    return
                result_urls = [
                    f"/api/material/characters/{character_id}/standard-photo/result-images/{name}"
                    for name in result_files
                ]
                repo.update_standard_photo_task(
                    task_id,
                    {
                        "status": "completed",
                        "error_message": None,
                        "result_images_json": json.dumps(result_urls, ensure_ascii=False),
                    },
                )
            except Exception as e:
                logger.error(f"标准照任务执行失败: {e}", exc_info=True)
                repo.update_standard_photo_task(
                    task_id,
                    {"status": "failed", "error_message": f"执行任务异常: {e}"},
                )
            finally:
                standard_photo_generation_service.cleanup_temp_images(temp_paths, temp_dir)
        finally:
            db.close()

    def get_standard_photo_task_status(self, character_id: str) -> Optional[Dict[str, Any]]:
        task = self.repo.get_standard_photo_task_by_character_id(character_id)
        if not task:
            return None
        try:
            selected_raw_image_ids = json.loads(task.selected_raw_image_ids_json or "[]")
            if not isinstance(selected_raw_image_ids, list):
                selected_raw_image_ids = []
        except json.JSONDecodeError:
            selected_raw_image_ids = []
        try:
            result_images = json.loads(task.result_images_json or "[]")
            if not isinstance(result_images, list):
                result_images = []
        except json.JSONDecodeError:
            result_images = []
        return {
            "task_id": task.id,
            "character_id": task.character_id,
            "shot_type": task.shot_type,
            "aspect_ratio": task.aspect_ratio,
            "output_count": task.output_count,
            "status": task.status,
            "error_message": task.error_message,
            "selected_raw_image_ids": selected_raw_image_ids,
            "result_images": result_images,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
        }

    def get_standard_photo_result_image_path(self, character_id: str, filename: str) -> Optional[str]:
        task = self.repo.get_standard_photo_task_by_character_id(character_id)
        if not task:
            return None
        return material_file_service.get_standard_photo_result_image_path(character_id, task.id, filename)

    def select_standard_photo_result(
        self, character_id: str, selected_result_filename: Optional[str], selected_result_index: Optional[int]
    ) -> MaterialCharacter:
        char = self.repo.get_by_id(character_id)
        if not char:
            raise ValueError("角色不存在")
        task = self.repo.get_standard_photo_task_by_character_id(character_id)
        if not task:
            raise ValueError("标准照任务不存在")
        if task.status != "completed":
            raise ValueError("标准照任务尚未完成")
        file_name: Optional[str] = selected_result_filename
        if not file_name and selected_result_index is not None:
            file_name = f"result_{selected_result_index}.png"
        if not file_name:
            raise ValueError("请选择要保存的结果图")
        path = material_file_service.get_standard_photo_result_image_path(character_id, task.id, file_name)
        if not path:
            raise ValueError("所选结果图不存在")

        url = self.standard_photo_result_image_url(character_id, file_name)
        updated = self.repo.save_official_photo_by_shot_type(character_id, task.shot_type, url)
        if not updated:
            raise ValueError("角色不存在")
        return updated
