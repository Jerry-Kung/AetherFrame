import asyncio
import json
import logging
import os
import uuid
from typing import Any, Dict, List, Optional, Tuple

from fastapi import BackgroundTasks
from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.models.material import (
    MaterialCharacter,
    MaterialCreativeDirection,
    MaterialCreativeDirectionTask,
    MaterialSeedPromptTask,
)
from app.prompts.material.standard_photo import (
    face_close_prompt,
    full_front_prompt,
    full_side_prompt,
    half_front_prompt,
    half_side_prompt,
)
from app.repositories.fixed_seed_template_repository import FixedSeedTemplateRepository
from app.repositories.material_repository import (
    INDEX_TO_SHOT_TYPE,
    MaterialCharacterRepository,
    MaterialCreativeDirectionRepository,
    MaterialCreativeDirectionTaskRepository,
    MaterialSeedPromptTaskRepository,
)
from app.utils.image_generation_timeout import (
    IMAGE_GEN_TIMEOUT_ERROR_MESSAGE,
    deadline_exceeded,
)
from app.config import (
    MATERIAL_CREATIVE_DIRECTION_PER_CHARACTER_LIMIT,
    MATERIAL_SEED_PROMPT_PER_CHARACTER_LIMIT,
    MATERIAL_SEED_PROMPT_PER_DIRECTION_LIMIT,
)
from app.services.material_service import chara_profile_generation_service
from app.services.material_service.creative_direction_generation_service import (
    run_creative_direction_task,
)
from app.services.material_service.seed_prompt_generation_service import (
    read_seed_draft_file,
    run_seed_prompt_task,
)
from app.services.material_service.task_concurrency import (
    assert_can_start_task,
    CreativeDirectionLimitExceededError,
    SeedPromptPerDirectionLimitExceededError,
    SeedPromptTotalLimitExceededError,
)
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
        self.fixed_seed_repo = FixedSeedTemplateRepository(db)
        self._direction_repo = MaterialCreativeDirectionRepository(db)
        self._direction_task_repo = MaterialCreativeDirectionTaskRepository(db)
        self._seed_task_repo = MaterialSeedPromptTaskRepository(db)

    def raw_image_url(self, character_id: str, stored_filename: str) -> str:
        return f"/api/material/characters/{character_id}/images/raw/{stored_filename}"

    def avatar_stored_image_url(self, character_id: str, stored_filename: str) -> str:
        return f"/api/material/characters/{character_id}/images/avatar/{stored_filename}"

    def avatar_url_for_character(self, character_id: str, avatar_filename: Optional[str]) -> str:
        """头像 URL：新数据在 images/avatar/；旧数据仍指向 raw 下的文件名。"""
        if not avatar_filename:
            return ""
        path = material_file_service.get_avatar_image_path(character_id, avatar_filename)
        if path:
            return self.avatar_stored_image_url(character_id, avatar_filename)
        return self.raw_image_url(character_id, avatar_filename)

    def standard_photo_result_image_url(self, character_id: str, filename: str) -> str:
        return f"/api/material/characters/{character_id}/standard-photo/result-images/{filename}"

    def standard_slot_image_url(self, character_id: str, shot_type: str) -> str:
        """已写入正式标准参考图的稳定 URL（按槽位/类型分文件）。"""
        return f"/api/material/characters/{character_id}/standard-photo/slot-images/{shot_type}"

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

    def _is_material_complete(self, char: MaterialCharacter) -> bool:
        """资料已完善：有设定说明、至少一张参考图、5 槽标准照齐全、已生成角色小档案正文。"""
        if not (char.setting_text or "").strip():
            return False
        from app.models.material import MaterialCharacterRawImage

        n_raw = self.db.query(MaterialCharacterRawImage).filter_by(character_id=char.id).count()
        if n_raw < 1:
            return False
        try:
            photos_raw = json.loads(char.official_photos_json or "[]")
        except json.JSONDecodeError:
            photos_raw = []
        slots = self._normalize_official_photos(photos_raw)
        if len(slots) != 5 or any(p is None for p in slots):
            return False
        try:
            bio = json.loads(char.bio_json or "{}")
        except json.JSONDecodeError:
            bio = {}
        if not isinstance(bio, dict):
            return False
        cp = bio.get("chara_profile")
        if not isinstance(cp, str) or not cp.strip():
            return False
        return True

    def _sync_material_completion_status(self, character_id: str) -> None:
        """满足完善条件时置为 done；不再满足时从 done 降为 draft/idle。"""
        char = self.repo.get_by_id(character_id)
        if not char:
            return
        complete = self._is_material_complete(char)
        if complete:
            if char.status != "done":
                self.repo.update(character_id, {"status": "done"})
        elif char.status == "done":
            has_setting = bool((char.setting_text or "").strip())
            from app.models.material import MaterialCharacterRawImage

            n = self.db.query(MaterialCharacterRawImage).filter_by(character_id=char.id).count()
            next_status = "draft" if (has_setting or n > 0) else "idle"
            self.repo.update(character_id, {"status": next_status})

    def _after_character_material_changed(self, character_id: str) -> None:
        self._sync_material_completion_status(character_id)
        char = self.repo.get_by_id(character_id)
        if char:
            self._maybe_promote_draft(char)
        self.repo.touch_character_updated_at(character_id)

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
        self._after_character_material_changed(character_id)
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
                avatar_url = self.avatar_url_for_character(c.id, c.avatar_filename)
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

    def update_setting_text(
        self, character_id: str, text: str, *, clear_setting_source: bool = False
    ) -> MaterialCharacter:
        char = self.repo.get_by_id(character_id)
        if not char:
            raise ValueError("角色不存在")
        updates: Dict[str, Any] = {"setting_text": text}
        if clear_setting_source:
            updates["setting_source_filename"] = None
        self.repo.update(character_id, updates)
        self._after_character_material_changed(character_id)
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
        base_fn = os.path.basename(fn.strip()) or None
        if base_fn and len(base_fn) > 255:
            base_fn = base_fn[:255]
        self.repo.update(
            character_id,
            {"setting_text": text, "setting_source_filename": base_fn},
        )
        self._after_character_material_changed(character_id)
        return self.repo.get_by_id(character_id)

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

        self._after_character_material_changed(character_id)
        return uploaded, failed

    def upload_character_avatar(self, character_id: str, file: UploadFile) -> MaterialCharacter:
        """将头像保存至独立 avatar 目录（与 raw 参考图分离），目录内仅保留一张。"""
        char = self.repo.get_by_id(character_id)
        if not char:
            raise ValueError("角色不存在")
        stored = material_file_service.save_avatar_image(character_id, file)
        self.repo.update(character_id, {"avatar_filename": stored})
        self._after_character_material_changed(character_id)
        return self.repo.get_by_id(character_id)

    def get_raw_image_path(self, character_id: str, filename: str) -> Optional[str]:
        char = self.repo.get_by_id(character_id)
        if not char:
            return None
        row = self.repo.get_raw_image_by_filename(character_id, filename)
        if not row:
            return None
        return material_file_service.get_raw_image_path(character_id, filename, row.type)

    def get_avatar_image_path(self, character_id: str, filename: str) -> Optional[str]:
        char = self.repo.get_by_id(character_id)
        if not char:
            return None
        return material_file_service.get_avatar_image_path(character_id, filename)

    def character_to_detail_dict(self, char: MaterialCharacter) -> Dict[str, Any]:
        from app.models.material import MaterialCharacterRawImage

        rows = (
            self.db.query(MaterialCharacterRawImage)
            .filter_by(character_id=char.id)
            .order_by(MaterialCharacterRawImage.created_at)
            .all()
        )
        from app.services.material_service.seed_meta_enrichment import (
            collect_direction_ids_from_bio,
            fetch_direction_meta_map,
        )

        bio_preview = self._parse_bio_safe(char.bio_json)
        dir_ids = collect_direction_ids_from_bio(bio_preview)
        dir_map = fetch_direction_meta_map(self.db, dir_ids) if dir_ids else {}
        return self._assemble_character_detail(char, rows, dir_map)

    @staticmethod
    def _parse_bio_safe(bio_json: Optional[str]) -> Dict[str, Any]:
        try:
            bio = json.loads(bio_json or "{}")
            if not isinstance(bio, dict):
                return {}
            return bio
        except json.JSONDecodeError:
            return {}

    def _assemble_character_detail(
        self,
        char: MaterialCharacter,
        raw_rows: List[Any],
        dir_map: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """供批量装配使用：raw_images + direction_meta 已由上层一次性查询。"""
        from app.services.material_service.seed_meta_enrichment import (
            enrich_seeds_with_direction_meta_from_map,
        )

        raw_images = []
        for r in raw_rows:
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
        bio = self._parse_bio_safe(char.bio_json)

        avatar_url = ""
        if char.avatar_filename:
            avatar_url = self.avatar_url_for_character(char.id, char.avatar_filename)

        detail = {
            "id": char.id,
            "name": char.name,
            "display_name": char.display_name or char.name,
            "avatar_url": avatar_url,
            "status": char.status,
            "updated_at": char.updated_at,
            "setting_text": char.setting_text or "",
            "setting_source_filename": char.setting_source_filename or "",
            "raw_images": raw_images,
            "official_photos": self._normalize_official_photos(official_photos),
            "bio": bio,
        }
        if isinstance(detail.get("bio"), dict):
            enrich_seeds_with_direction_meta_from_map(detail["bio"], dir_map)
        return detail

    def get_characters_batch_details(self, character_ids: List[str]) -> List[Dict[str, Any]]:
        """批量获取多个角色的完整详情，用于前端一次性加载。
        3 次 SQL：chars + raw_images IN + creative_directions IN。
        """
        if not character_ids:
            return []
        chars = self.repo.get_by_ids(character_ids)
        if not chars:
            return []

        from app.services.material_service.seed_meta_enrichment import (
            collect_direction_ids_from_bio,
            fetch_direction_meta_map,
        )

        ids = [c.id for c in chars]
        raw_map = self.repo.list_raw_images_by_character_ids(ids)
        all_dir_ids: set = set()
        for c in chars:
            bio = self._parse_bio_safe(c.bio_json)
            all_dir_ids.update(collect_direction_ids_from_bio(bio))
        dir_map = fetch_direction_meta_map(self.db, all_dir_ids) if all_dir_ids else {}

        return [
            self._assemble_character_detail(c, raw_map.get(c.id, []), dir_map)
            for c in chars
        ]

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
        if task.status in ("pending", "processing"):
            if deadline_exceeded(task.updated_at, task.output_count):
                task = self.repo.update_standard_photo_task(
                    task.id,
                    {
                        "status": "failed",
                        "error_message": IMAGE_GEN_TIMEOUT_ERROR_MESSAGE,
                    },
                )
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

    def get_standard_slot_image_path(self, character_id: str, shot_type: str) -> Optional[str]:
        return material_file_service.get_standard_slot_image_path(character_id, shot_type)

    def clear_official_photo_slot(self, character_id: str, slot_index: int) -> MaterialCharacter:
        char = self.repo.get_by_id(character_id)
        if not char:
            raise ValueError("角色不存在")
        shot_type = INDEX_TO_SHOT_TYPE.get(slot_index)
        if shot_type is None:
            raise ValueError("标准照槽位索引无效")
        updated = self.repo.clear_official_photo_at_index(character_id, slot_index)
        if not updated:
            raise ValueError("角色不存在")
        material_file_service.delete_standard_slot_image_file(character_id, shot_type)
        self._after_character_material_changed(character_id)
        return self.repo.get_by_id(character_id)

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

        try:
            material_file_service.copy_task_result_to_official_slot(
                character_id, task.id, file_name, task.shot_type
            )
        except OSError as e:
            logger.error(f"复制标准照到正式槽位失败: {e}", exc_info=True)
            raise ValueError("写入正式标准照失败") from e
        url = self.standard_slot_image_url(character_id, task.shot_type)
        updated = self.repo.save_official_photo_by_shot_type(character_id, task.shot_type, url)
        if not updated:
            raise ValueError("角色不存在")
        self._after_character_material_changed(character_id)
        return self.repo.get_by_id(character_id)

    async def _run_chara_profile_task_async(self, character_id: str, task_id: str) -> None:
        await asyncio.to_thread(self._run_chara_profile_task_sync, character_id, task_id)

    def start_chara_profile_task(
        self,
        character_id: str,
        selected_fanart_ids: List[str],
        background_tasks: Optional[BackgroundTasks] = None,
    ) -> Dict[str, Any]:
        char = self.repo.get_by_id(character_id)
        if not char:
            raise ValueError("角色不存在")
        if not (char.setting_text or "").strip():
            raise ValueError("请先填写角色人设说明")
        official_image_list: List[str] = []
        for i in range(5):
            st = INDEX_TO_SHOT_TYPE[i]
            p = material_file_service.get_standard_slot_image_path(character_id, st)
            if not p:
                raise ValueError("请先完成全部5种标准参考照并保存到正式槽位")
            official_image_list.append(p)
        if not selected_fanart_ids:
            raise ValueError("请至少选择一张同人立绘")
        if len(selected_fanart_ids) > 5:
            raise ValueError("同人立绘一次最多选择5张")
        for image_id in selected_fanart_ids:
            row = self.repo.get_raw_image(character_id, image_id)
            if not row or row.type != "fanart":
                raise ValueError("存在无效的同人立绘选择")
            path = material_file_service.get_raw_image_path(
                character_id, row.stored_filename, row.type
            )
            if not path or not os.path.isfile(path):
                raise ValueError("同人立绘文件不存在，请重新上传")

        material_file_service.clear_chara_profile_artifacts(character_id)
        task = self.repo.upsert_chara_profile_task(
            character_id=character_id,
            selected_fanart_ids=selected_fanart_ids,
            status="processing",
            error_message=None,
            current_step=None,
        )

        if background_tasks:
            background_tasks.add_task(self._run_chara_profile_task_async, character_id, task.id)
        else:
            self._run_chara_profile_task_sync(character_id, task.id)

        task = self.repo.get_chara_profile_task_by_id(task.id)
        return {"task_id": task.id, "status": task.status}

    def _run_chara_profile_task_sync(self, character_id: str, task_id: str) -> None:
        bind = self.db.get_bind()
        db = Session(bind=bind, autocommit=False, autoflush=False)
        try:
            repo = MaterialCharacterRepository(db)
            task = repo.get_chara_profile_task_by_id(task_id)
            if not task:
                return
            char = repo.get_by_id(character_id)
            if not char:
                repo.update_chara_profile_task(
                    task_id,
                    {"status": "failed", "error_message": "角色不存在", "current_step": None},
                )
                return

            official_image_list = (
                material_file_service.standard_reference_paths_for_multimodal_prompt(
                    character_id
                )
            )
            if not official_image_list:
                repo.update_chara_profile_task(
                    task_id,
                    {
                        "status": "failed",
                        "error_message": "标准参考图槽位文件缺失",
                        "current_step": None,
                    },
                )
                return

            try:
                selected_ids = json.loads(task.selected_fanart_ids_json or "[]")
                if not isinstance(selected_ids, list):
                    selected_ids = []
            except json.JSONDecodeError:
                selected_ids = []

            fanart_image_list: List[str] = []
            for image_id in selected_ids:
                row = repo.get_raw_image(character_id, str(image_id))
                if not row or row.type != "fanart":
                    repo.update_chara_profile_task(
                        task_id,
                        {"status": "failed", "error_message": "同人立绘记录无效", "current_step": None},
                    )
                    return
                path = material_file_service.get_raw_image_path(
                    character_id, row.stored_filename, row.type
                )
                if not path or not os.path.isfile(path):
                    repo.update_chara_profile_task(
                        task_id,
                        {"status": "failed", "error_message": "同人立绘文件缺失", "current_step": None},
                    )
                    return
                fanart_image_list.append(path)

            if not fanart_image_list:
                repo.update_chara_profile_task(
                    task_id,
                    {"status": "failed", "error_message": "没有可用的同人立绘文件", "current_step": None},
                )
                return

            def on_step(step: str) -> None:
                repo.update_chara_profile_task(task_id, {"current_step": step})

            try:
                final_md = chara_profile_generation_service.run_chara_profile_pipeline(
                    character_id=character_id,
                    persona_text=char.setting_text or "",
                    official_image_list=official_image_list,
                    fanart_image_list=fanart_image_list,
                    on_step=on_step,
                )
            except Exception as e:
                logger.error(f"角色小档案任务执行失败: {e}", exc_info=True)
                repo.update_chara_profile_task(
                    task_id,
                    {"status": "failed", "error_message": str(e), "current_step": None},
                )
                return

            try:
                bio = json.loads(char.bio_json or "{}")
                if not isinstance(bio, dict):
                    bio = {}
            except json.JSONDecodeError:
                bio = {}
            bio["chara_profile"] = final_md
            repo.update(character_id, {"bio_json": json.dumps(bio, ensure_ascii=False)})
            MaterialService(db)._after_character_material_changed(character_id)
            repo.update_chara_profile_task(
                task_id,
                {
                    "status": "completed",
                    "error_message": None,
                    "current_step": "done",
                },
            )
        finally:
            db.close()

    def get_chara_profile_task_status(self, character_id: str) -> Optional[Dict[str, Any]]:
        task = self.repo.get_chara_profile_task_by_character_id(character_id)
        if not task:
            return None
        try:
            selected_fanart_ids = json.loads(task.selected_fanart_ids_json or "[]")
            if not isinstance(selected_fanart_ids, list):
                selected_fanart_ids = []
        except json.JSONDecodeError:
            selected_fanart_ids = []
        return {
            "task_id": task.id,
            "character_id": task.character_id,
            "status": task.status,
            "error_message": task.error_message,
            "current_step": task.current_step,
            "selected_fanart_ids": selected_fanart_ids,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
        }

    def patch_character_bio(
        self,
        character_id: str,
        chara_profile: Optional[str] = None,
        official_seed_prompts: Optional[Dict[str, Any]] = None,
    ) -> MaterialCharacter:
        char = self.repo.get_by_id(character_id)
        if not char:
            raise ValueError("角色不存在")
        if chara_profile is None and official_seed_prompts is None:
            raise ValueError("至少提供 chara_profile、official_seed_prompts 之一")
        try:
            bio = json.loads(char.bio_json or "{}")
            if not isinstance(bio, dict):
                bio = {}
        except json.JSONDecodeError:
            bio = {}
        if chara_profile is not None:
            bio["chara_profile"] = chara_profile
        if official_seed_prompts is not None:
            cs = official_seed_prompts.get("character_specific")
            ge = official_seed_prompts.get("general")
            if isinstance(ge, list):
                for entry in ge:
                    if isinstance(entry, dict):
                        entry.pop("creative_direction_id", None)
            if (
                isinstance(cs, list)
                and isinstance(ge, list)
                and len(cs) == 0
                and len(ge) == 0
            ):
                bio.pop("official_seed_prompts", None)
            else:
                bio["official_seed_prompts"] = official_seed_prompts
        self.repo.update(character_id, {"bio_json": json.dumps(bio, ensure_ascii=False)})
        self._after_character_material_changed(character_id)
        updated = self.repo.get_by_id(character_id)
        if not updated:
            raise ValueError("角色不存在")
        return updated

    def start_creative_direction_task(
        self,
        character_id: str,
        divergence: str,
        initial_input: Optional[str],
        background_tasks: BackgroundTasks,
    ) -> MaterialCreativeDirectionTask:
        char = self.repo.get_by_id(character_id)
        if char is None:
            raise ValueError("character not found")

        n_directions = self._direction_repo.count_by_character(character_id)
        if n_directions >= MATERIAL_CREATIVE_DIRECTION_PER_CHARACTER_LIMIT:
            raise CreativeDirectionLimitExceededError()

        assert_can_start_task(self.db, character_id)

        task = MaterialCreativeDirectionTask(
            id=str(uuid.uuid4()),
            character_id=character_id,
            status="pending",
            divergence=divergence,
            initial_input=initial_input or None,
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)

        background_tasks.add_task(run_creative_direction_task, task.id)
        return task

    def get_creative_direction_task_status(
        self, character_id: str, task_id: str
    ) -> Tuple[MaterialCreativeDirectionTask, Optional[MaterialCreativeDirection]]:
        task = self._direction_task_repo.get_by_id(task_id)
        if task is None or task.character_id != character_id:
            raise ValueError("task not found")
        direction = None
        if task.status == "completed" and task.result_direction_id:
            direction = self._direction_repo.get_by_id(task.result_direction_id)
        return task, direction

    def list_creative_directions(self, character_id: str) -> List[MaterialCreativeDirection]:
        return self._direction_repo.list_by_character(character_id)

    def patch_creative_direction(
        self,
        character_id: str,
        direction_id: str,
        title: Optional[str],
        description: Optional[str],
    ) -> MaterialCreativeDirection:
        row = self._direction_repo.get_by_id(direction_id)
        if row is None or row.character_id != character_id:
            raise ValueError("direction not found")
        if title is not None:
            row.title = title
        if description is not None:
            row.description = description
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_creative_direction(self, character_id: str, direction_id: str) -> None:
        row = self._direction_repo.get_by_id(direction_id)
        if row is None or row.character_id != character_id:
            raise ValueError("direction not found")
        self.db.delete(row)
        self.db.commit()
        self._detach_seeds_from_direction(character_id, direction_id)
        try:
            path = os.path.join(
                material_file_service.get_character_dir(character_id),
                "creative_directions",
                f"{direction_id}.json",
            )
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            logger.warning("failed to delete direction json file: %s", e)

    def _detach_seeds_from_direction(self, character_id: str, direction_id: str) -> None:
        """方向被删后，把 bio_json 中绑定到该方向的种子转为「默认世界观」(creative_direction_id=None)。"""
        char = self.repo.get_by_id(character_id)
        if not char:
            return
        try:
            bio = json.loads(char.bio_json or "{}")
            if not isinstance(bio, dict):
                return
        except json.JSONDecodeError:
            return
        seeds = bio.get("official_seed_prompts")
        if not isinstance(seeds, dict):
            return
        cs = seeds.get("character_specific")
        if not isinstance(cs, list):
            return
        changed = False
        for entry in cs:
            if isinstance(entry, dict) and entry.get("creative_direction_id") == direction_id:
                entry["creative_direction_id"] = None
                changed = True
        if not changed:
            return
        self.repo.update(character_id, {"bio_json": json.dumps(bio, ensure_ascii=False)})

    def is_direction_owned_by_character(self, direction_id: str, character_id: str) -> bool:
        row = self._direction_repo.get_by_id(direction_id)
        return row is not None and row.character_id == character_id

    def start_seed_prompt_task(
        self,
        character_id: str,
        creative_direction_id: Optional[str],
        background_tasks: BackgroundTasks,
    ) -> MaterialSeedPromptTask:
        """提交种子提示词生成任务。"""
        char = self.repo.get_by_id(character_id)
        if char is None:
            raise ValueError("character not found")

        if creative_direction_id is not None:
            dir_row = self._direction_repo.get_by_id(creative_direction_id)
            if dir_row is None or dir_row.character_id != character_id:
                raise ValueError("creative_direction not found")

        bio = json.loads(char.bio_json or "{}")
        cs = (bio.get("official_seed_prompts") or {}).get("character_specific") or []
        total = sum(1 for x in cs if isinstance(x, dict))
        if total >= MATERIAL_SEED_PROMPT_PER_CHARACTER_LIMIT:
            raise SeedPromptTotalLimitExceededError()

        same_dir_count = sum(
            1
            for x in cs
            if isinstance(x, dict) and x.get("creative_direction_id") == creative_direction_id
        )
        if same_dir_count >= MATERIAL_SEED_PROMPT_PER_DIRECTION_LIMIT:
            raise SeedPromptPerDirectionLimitExceededError()

        assert_can_start_task(self.db, character_id)

        task = MaterialSeedPromptTask(
            id=str(uuid.uuid4()),
            character_id=character_id,
            creative_direction_id=creative_direction_id,
            status="pending",
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)

        background_tasks.add_task(run_seed_prompt_task, task.id)
        return task

    def get_seed_prompt_task_status(
        self, character_id: str, task_id: str
    ) -> Tuple[MaterialSeedPromptTask, Optional[dict]]:
        """返回 (task_row, seed_draft_dict?)；draft 仅在 completed 时回填。"""
        task = self._seed_task_repo.get_by_id(task_id)
        if task is None or task.character_id != character_id:
            raise ValueError("task not found")
        draft = None
        if task.status == "completed":
            draft = read_seed_draft_file(character_id, task_id)
        return task, draft

    # --- 固定种子模板（全角色共享） ---

    def list_fixed_seed_templates(self) -> List[Dict[str, Any]]:
        return [self.fixed_seed_repo.row_to_dict(r) for r in self.fixed_seed_repo.list_all()]

    def create_fixed_seed_template(self, text: str) -> Dict[str, Any]:
        t = (text or "").strip()
        if not t:
            raise ValueError("固定模板正文不能为空")
        row = self.fixed_seed_repo.create(t)
        return self.fixed_seed_repo.row_to_dict(row)

    def patch_fixed_seed_template(
        self,
        template_id: str,
        *,
        text: Optional[str] = None,
        used: Optional[bool] = None,
    ) -> Dict[str, Any]:
        if text is None and used is None:
            raise ValueError("至少提供 text 或 used 之一")
        new_text = (text.strip() if isinstance(text, str) else None)
        if new_text is not None and not new_text:
            raise ValueError("固定模板正文不能为空")
        row = self.fixed_seed_repo.update(template_id, text=new_text, used=used)
        if not row:
            raise ValueError("固定模板不存在")
        return self.fixed_seed_repo.row_to_dict(row)

    def delete_fixed_seed_template(self, template_id: str) -> None:
        if not self.fixed_seed_repo.delete(template_id):
            raise ValueError("固定模板不存在")

    def clear_fixed_seed_templates(self) -> int:
        return self.fixed_seed_repo.delete_all()

    def list_fixed_unused_seed_texts(self) -> List[str]:
        out: List[str] = []
        for row in self.fixed_seed_repo.list_unused():
            s = (row.text or "").strip()
            if s:
                out.append(s)
        return out
