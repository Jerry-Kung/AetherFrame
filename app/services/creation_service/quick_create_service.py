import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.models.database import SessionLocal
from app.repositories.creation_repository import (
    CreationPromptPrecreationRepository,
    CreationQuickCreateRepository,
)
from app.repositories.material_repository import SHOT_TYPE_TO_INDEX
from app.repositories.material_repository import MaterialCharacterRepository
from app.services import directory_service
from app.services.material_service.material_file_service import get_standard_slot_image_path
from app.tools.llm.nano_banana_pro import generate_image_with_nano_banana_pro

logger = logging.getLogger(__name__)

VALID_ASPECT_RATIOS = {"16:9", "4:3", "1:1", "3:4", "9:16"}


def _write_json(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _safe_segment(value: str) -> str:
    out = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in (value or ""))
    return out[:40] or "prompt"


def _resolve_standard_reference_paths(character_id: str) -> List[str]:
    refs: List[str] = []
    for shot_type in SHOT_TYPE_TO_INDEX.keys():
        path = get_standard_slot_image_path(character_id, shot_type)
        if not path or not os.path.isfile(path):
            raise ValueError(f"角色标准参考图不足 5 张，请先补齐标准照（缺少: {shot_type}）")
        refs.append(path)
    return refs


def _resolve_selected_prompts(
    *,
    selected_prompts: List[Dict[str, str]],
    latest_cards: List[Dict[str, Any]],
) -> List[Dict[str, str]]:
    card_map: Dict[str, Dict[str, Any]] = {}
    for c in latest_cards:
        cid = str(c.get("id") or "").strip()
        if cid:
            card_map[cid] = c

    if not selected_prompts:
        out: List[Dict[str, str]] = []
        for c in latest_cards:
            pid = str(c.get("id") or "").strip()
            fp = str(c.get("fullPrompt") or "").strip()
            if pid and fp:
                out.append({"id": pid, "fullPrompt": fp})
        return out

    out: List[Dict[str, str]] = []
    for item in selected_prompts:
        pid = str(item.get("id") or "").strip()
        passed_full = str(item.get("fullPrompt") or "").strip()
        resolved_full = ""
        if pid and pid in card_map:
            resolved_full = str(card_map[pid].get("fullPrompt") or "").strip()
            if passed_full and passed_full != resolved_full:
                logger.warning("一键创作 Prompt 文本与预生成记录不一致，使用记录值: prompt_id=%s", pid)
        else:
            resolved_full = passed_full
            if pid:
                logger.warning("一键创作 Prompt ID 未命中最新预生成记录，回退使用入参文本: prompt_id=%s", pid)

        if not resolved_full:
            continue
        out.append({"id": pid or f"manual_{len(out) + 1}", "fullPrompt": resolved_full})
    return out


def run_quick_create_task_sync(task_id: str, session_factory=SessionLocal) -> None:
    db = session_factory()
    try:
        qrepo = CreationQuickCreateRepository(db)
        prepo = CreationPromptPrecreationRepository(db)
        mrepo = MaterialCharacterRepository(db)

        task = qrepo.get_by_id(task_id)
        if not task:
            return
        char = mrepo.get_by_id(task.character_id)
        if not char:
            qrepo.update(task_id, {"status": "failed", "error_message": "角色不存在", "current_step": None})
            return

        qrepo.update(task_id, {"status": "running", "current_step": "preparing", "error_message": None})
        directory_service.ensure_dir_exists(task.work_dir)

        refs = _resolve_standard_reference_paths(task.character_id)
        latest = prepo.get_latest_completed_by_character_id(task.character_id)
        latest_cards: List[Dict[str, Any]] = []
        if latest and latest.result_json:
            try:
                parsed = json.loads(latest.result_json)
                if isinstance(parsed, list):
                    latest_cards = parsed
            except json.JSONDecodeError:
                latest_cards = []

        try:
            selected_raw = json.loads(task.selected_prompts_json or "[]")
            if not isinstance(selected_raw, list):
                selected_raw = []
        except json.JSONDecodeError:
            selected_raw = []
        selected: List[Dict[str, str]] = _resolve_selected_prompts(
            selected_prompts=[x for x in selected_raw if isinstance(x, dict)],
            latest_cards=latest_cards,
        )
        if not selected:
            raise ValueError("没有可用于一键创作的 Prompt")

        task_meta = {
            "task_id": task.id,
            "character_id": task.character_id,
            "n": task.n,
            "aspect_ratio": task.aspect_ratio,
            "selected_prompts": selected,
            "reference_images": refs,
            "created_at": datetime.now().isoformat(),
        }
        _write_json(os.path.join(task.work_dir, "task_meta.json"), task_meta)

        qrepo.update(task_id, {"current_step": "generating"})
        results: List[Dict[str, Any]] = []
        total_success = 0
        for idx, item in enumerate(selected):
            prompt_id = item["id"]
            full_prompt = item["fullPrompt"]
            prompt_dir = os.path.join(task.work_dir, f"prompt_{idx + 1}_{_safe_segment(prompt_id)}")
            directory_service.ensure_dir_exists(prompt_dir)

            content = [{"text": full_prompt}, {"text": "以下是角色参考图，作为你修补任务的重要参考"}]
            for p in refs:
                content.append({"picture": p})

            attempts = 0
            success = 0
            images: List[str] = []
            max_attempts = 2 * task.n
            while success < task.n and attempts < max_attempts:
                attempts += 1
                file_name = f"image_{success + 1}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.png"
                ok = generate_image_with_nano_banana_pro(
                    Content=content,
                    output_path=prompt_dir,
                    file_name=file_name,
                    aspect_ratio=task.aspect_ratio,
                )
                if not ok:
                    continue
                full_path = os.path.join(prompt_dir, file_name)
                if os.path.isfile(full_path):
                    success += 1
                    total_success += 1
                    images.append(os.path.relpath(full_path, task.work_dir))

            results.append(
                {
                    "prompt_id": prompt_id,
                    "full_prompt": full_prompt,
                    "attempt_count": attempts,
                    "success_count": success,
                    "requested_count": task.n,
                    "generated_images": images,
                }
            )

        _write_json(os.path.join(task.work_dir, "result.json"), results)
        if total_success <= 0:
            qrepo.update(task_id, {"status": "failed", "error_message": "所有 Prompt 均生成失败", "current_step": None})
            return

        qrepo.update(
            task_id,
            {
                "status": "completed",
                "current_step": None,
                "error_message": None,
                "result_json": results,
            },
        )
    except Exception as e:
        logger.error("一键创作任务失败 task_id=%s: %s", task_id, e, exc_info=True)
        msg = str(e) if str(e) else type(e).__name__
        try:
            qrepo = CreationQuickCreateRepository(db)
            if qrepo.get_by_id(task_id):
                qrepo.update(task_id, {"status": "failed", "error_message": msg, "current_step": None})
        except Exception:
            logger.exception("写入一键创作失败状态时出错")
    finally:
        db.close()


class QuickCreateService:
    def __init__(self, db: Session):
        self.db = db
        self.quick_repo = CreationQuickCreateRepository(db)
        self.pre_repo = CreationPromptPrecreationRepository(db)
        self.material_repo = MaterialCharacterRepository(db)
        bind = self.db.get_bind()
        self._session_factory = lambda: Session(bind=bind, autocommit=False, autoflush=False)

    async def _run_task_async(self, task_id: str) -> None:
        await asyncio.to_thread(run_quick_create_task_sync, task_id, self._session_factory)

    def start_quick_create(
        self,
        *,
        character_id: str,
        selected_prompts: List[Dict[str, str]],
        n: int,
        aspect_ratio: str,
        background_tasks: Optional[BackgroundTasks] = None,
    ) -> Dict[str, Any]:
        if n < 1 or n > 4:
            raise ValueError("生成数量必须在 1 到 4 之间")
        if aspect_ratio not in VALID_ASPECT_RATIOS:
            raise ValueError("aspect_ratio 不合法")
        char = self.material_repo.get_by_id(character_id)
        if not char:
            raise ValueError("角色不存在")

        # 预检查，尽早返回业务错误
        _resolve_standard_reference_paths(character_id)
        latest = self.pre_repo.get_latest_completed_by_character_id(character_id)
        if not latest:
            raise ValueError("未找到可用的 Prompt 预生成结果")
        cards = json.loads(latest.result_json or "[]")
        resolved = _resolve_selected_prompts(
            selected_prompts=selected_prompts,
            latest_cards=cards if isinstance(cards, list) else [],
        )
        if not resolved:
            raise ValueError("未选择有效 Prompt")

        task = self.quick_repo.create(
            character_id=character_id,
            n=n,
            aspect_ratio=aspect_ratio,
            selected_prompts=selected_prompts,
            status="pending",
        )
        directory_service.ensure_dir_exists(task.work_dir)

        # BackgroundTasks may evaluate to False when currently empty.
        # We only need to check whether it is provided by FastAPI.
        if background_tasks is not None:
            background_tasks.add_task(self._run_task_async, task.id)
        else:
            run_quick_create_task_sync(task.id, self._session_factory)

        task = self.quick_repo.get_by_id(task.id)
        return {"task_id": task.id, "status": task.status if task else "pending"}

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        task = self.quick_repo.get_by_id(task_id)
        if not task:
            return None
        results = None
        if task.result_json:
            try:
                parsed = json.loads(task.result_json)
                if isinstance(parsed, list):
                    results = parsed
            except json.JSONDecodeError:
                results = None
        return {
            "task_id": task.id,
            "character_id": task.character_id,
            "status": task.status,
            "error_message": task.error_message,
            "current_step": task.current_step,
            "n": task.n,
            "aspect_ratio": task.aspect_ratio,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
            "results": results,
        }

    def get_task_image_path(self, task_id: str, image_path: str) -> Optional[str]:
        task = self.quick_repo.get_by_id(task_id)
        if not task:
            return None
        rel = (image_path or "").strip().replace("\\", "/")
        if not rel:
            return None
        candidate = os.path.realpath(os.path.join(task.work_dir, rel))
        root = os.path.realpath(task.work_dir)
        if not candidate.startswith(root + os.sep) and candidate != root:
            return None
        if not os.path.isfile(candidate):
            return None
        return candidate
