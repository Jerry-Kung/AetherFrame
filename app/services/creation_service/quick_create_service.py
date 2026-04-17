import asyncio
import json
import logging
import os
import shutil
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.models.database import SessionLocal
from app.repositories.creation_repository import (
    CreationPromptPrecreationRepository,
    CreationQuickCreateRepository,
)
from app.repositories.material_repository import MaterialCharacterRepository
from app.services import directory_service
from app.services.material_service.material_file_service import (
    standard_reference_paths_for_multimodal_prompt,
)
from app.tools.llm.nano_banana_pro import generate_image_with_nano_banana_pro
from app.tools.llm.yibu_llm_infer import yibu_gemini_infer
from app.prompts.creation.prompt_review import prompt_review

logger = logging.getLogger(__name__)

VALID_ASPECT_RATIOS = {"16:9", "4:3", "1:1", "3:4", "9:16"}
DEFAULT_HISTORY_LIMIT = 50


def _write_json(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _dump_json_atomic(path: str, payload: Any) -> None:
    directory_service.ensure_dir_exists(os.path.dirname(path))
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _to_iso(dt: Optional[datetime]) -> str:
    if dt is None:
        return ""
    return dt.isoformat()


def _parse_json_list(raw: Optional[str]) -> List[Dict[str, Any]]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [x for x in parsed if isinstance(x, dict)]
    except json.JSONDecodeError:
        return []
    return []


def _parse_llm_json_object(text: str) -> Dict[str, Any]:
    s = (text or "").strip()
    if s.startswith("```"):
        lines = s.split("\n")
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        s = "\n".join(lines).strip()
    start = s.find("{")
    end = s.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("响应中未找到可解析的 JSON 对象")
    return json.loads(s[start : end + 1])


def _review_generated_image(
    *,
    full_path: str,
    seed_prompt: str,
    creation_prompt: str,
) -> tuple[bool, str]:
    image_path = [full_path]
    prompt = prompt_review.format(
        seed_prompt=seed_prompt,
        creation_prompt=creation_prompt,
    )
    response = yibu_gemini_infer(prompt, image_path=image_path, thinking_level="high")
    parsed = _parse_llm_json_object(response)
    review_result = bool(parsed.get("review_result", False))
    review_reason = str(parsed.get("review_reason") or "").strip()
    return review_result, review_reason


def _archive_rejected_image(
    *,
    task_work_dir: str,
    prompt_id: str,
    full_path: str,
    review_result: bool,
    review_reason: str,
) -> None:
    junk_dir = os.path.join(task_work_dir, "junk_images")
    directory_service.ensure_dir_exists(junk_dir)

    original_name = os.path.basename(full_path)
    safe_prompt_id = _safe_segment(prompt_id)
    unique_name = f"{safe_prompt_id}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_{original_name}"
    archived_image_path = os.path.join(junk_dir, unique_name)
    shutil.move(full_path, archived_image_path)

    review_payload = {
        "prompt_id": prompt_id,
        "review_result": review_result,
        "review_reason": review_reason,
        "original_image_path": full_path,
        "archived_image_path": archived_image_path,
        "created_at": datetime.now().isoformat(),
    }
    review_file_path = f"{archived_image_path}.review.json"
    _write_json(review_file_path, review_payload)


def _sync_quick_create_history_files_for_task_id(db: Session, task_id: str) -> None:
    qrepo = CreationQuickCreateRepository(db)
    mrepo = MaterialCharacterRepository(db)
    task = qrepo.get_by_id(task_id)
    if not task:
        return

    directory_service.ensure_dir_exists(
        directory_service.get_quick_create_history_dir()
    )
    directory_service.ensure_dir_exists(
        directory_service.get_quick_create_history_records_dir()
    )

    character = mrepo.get_by_id(task.character_id)
    chara_name = character.name if character else "未知角色"
    selected_prompts = _parse_json_list(task.selected_prompts_json)
    results = _parse_json_list(task.result_json)
    image_count = sum(
        len((r.get("generated_images") or [])) for r in results if isinstance(r, dict)
    )
    record_payload = {
        "id": task.id,
        "task_id": task.id,
        "character_id": task.character_id,
        "seed_prompt": task.seed_prompt,
        "chara_name": chara_name,
        "chara_avatar": "",
        "prompt_count": len(selected_prompts),
        "image_count": image_count,
        "n": task.n,
        "aspect_ratio": task.aspect_ratio,
        "status": task.status,
        "error_message": task.error_message,
        "created_at": _to_iso(task.created_at),
        "updated_at": _to_iso(task.updated_at),
        "selected_prompts": selected_prompts,
        "results": results,
    }
    _dump_json_atomic(
        directory_service.get_quick_create_history_record_path(task.id), record_payload
    )

    tasks = qrepo.list_history(limit=2000, offset=0)
    items: List[Dict[str, Any]] = []
    for t in tasks:
        c = mrepo.get_by_id(t.character_id)
        selected = _parse_json_list(t.selected_prompts_json)
        result_list = _parse_json_list(t.result_json)
        image_total = sum(
            len((r.get("generated_images") or []))
            for r in result_list
            if isinstance(r, dict)
        )
        items.append(
            {
                "id": t.id,
                "task_id": t.id,
                "character_id": t.character_id,
                "seed_prompt": t.seed_prompt,
                "chara_name": c.name if c else "未知角色",
                "chara_avatar": "",
                "prompt_count": len(selected),
                "image_count": image_total,
                "n": t.n,
                "aspect_ratio": t.aspect_ratio,
                "status": t.status,
                "error_message": t.error_message,
                "created_at": _to_iso(t.created_at),
                "updated_at": _to_iso(t.updated_at),
            }
        )
    _dump_json_atomic(
        directory_service.get_quick_create_history_index_path(),
        {"updated_at": datetime.now().isoformat(), "total": len(items), "items": items},
    )


def _safe_segment(value: str) -> str:
    out = "".join(
        ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in (value or "")
    )
    return out[:40] or "prompt"


def _resolve_standard_reference_paths(character_id: str) -> List[str]:
    refs = standard_reference_paths_for_multimodal_prompt(character_id)
    if not refs:
        raise ValueError("角色标准参考图不足 5 张，请先补齐标准照")
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
                logger.warning(
                    "一键创作 Prompt 文本与预生成记录不一致，使用记录值: prompt_id=%s",
                    pid,
                )
        else:
            resolved_full = passed_full
            if pid:
                logger.warning(
                    "一键创作 Prompt ID 未命中最新预生成记录，回退使用入参文本: prompt_id=%s",
                    pid,
                )

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
            qrepo.update(
                task_id,
                {
                    "status": "failed",
                    "error_message": "角色不存在",
                    "current_step": None,
                },
            )
            _sync_quick_create_history_files_for_task_id(db, task_id)
            return

        qrepo.update(
            task_id,
            {"status": "running", "current_step": "preparing", "error_message": None},
        )
        _sync_quick_create_history_files_for_task_id(db, task_id)
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
            "seed_prompt": task.seed_prompt,
            "n": task.n,
            "aspect_ratio": task.aspect_ratio,
            "selected_prompts": selected,
            "reference_images": refs,
            "created_at": datetime.now().isoformat(),
        }
        _write_json(os.path.join(task.work_dir, "task_meta.json"), task_meta)

        qrepo.update(task_id, {"current_step": "generating"})
        _sync_quick_create_history_files_for_task_id(db, task_id)
        results: List[Dict[str, Any]] = []
        total_success = 0
        for idx, item in enumerate(selected):
            prompt_id = item["id"]
            full_prompt = item["fullPrompt"]
            prompt_dir = os.path.join(
                task.work_dir, f"prompt_{idx + 1}_{_safe_segment(prompt_id)}"
            )
            directory_service.ensure_dir_exists(prompt_dir)

            content = [
                {"text": full_prompt},
                {"text": "以下是角色参考图，作为你修补任务的重要参考"},
            ]
            for p in refs:
                content.append({"picture": p})

            attempts = 0
            success = 0
            images: List[str] = []
            max_attempts = 3 * task.n
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
                    try:
                        reviewed, reason = _review_generated_image(
                            full_path=full_path,
                            seed_prompt=task.seed_prompt,
                            creation_prompt=full_prompt,
                        )
                    except Exception as e:
                        logger.warning(
                            "图片审核异常，按不通过处理: task_id=%s prompt_id=%s file=%s error=%s",
                            task_id,
                            prompt_id,
                            full_path,
                            e,
                            exc_info=True,
                        )
                        reviewed, reason = False, f"审核异常: {e}"

                    if reviewed:
                        success += 1
                        total_success += 1
                        images.append(os.path.relpath(full_path, task.work_dir))
                    else:
                        logger.info(
                            "图片审核不通过，归档到 junk_images 并重试: task_id=%s prompt_id=%s file=%s reason=%s",
                            task_id,
                            prompt_id,
                            full_path,
                            reason or "未提供",
                        )
                        try:
                            _archive_rejected_image(
                                task_work_dir=task.work_dir,
                                prompt_id=prompt_id,
                                full_path=full_path,
                                review_result=False,
                                review_reason=reason or "未提供",
                            )
                        except FileNotFoundError:
                            pass
                        except Exception:
                            logger.warning(
                                "归档审核失败图片出错: %s", full_path, exc_info=True
                            )

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
            qrepo.update(
                task_id,
                {
                    "status": "failed",
                    "error_message": "所有 Prompt 均生成失败",
                    "current_step": None,
                },
            )
            _sync_quick_create_history_files_for_task_id(db, task_id)
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
        _sync_quick_create_history_files_for_task_id(db, task_id)
    except Exception as e:
        logger.error("一键创作任务失败 task_id=%s: %s", task_id, e, exc_info=True)
        msg = str(e) if str(e) else type(e).__name__
        try:
            qrepo = CreationQuickCreateRepository(db)
            if qrepo.get_by_id(task_id):
                qrepo.update(
                    task_id,
                    {"status": "failed", "error_message": msg, "current_step": None},
                )
                _sync_quick_create_history_files_for_task_id(db, task_id)
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
        self._session_factory = lambda: Session(
            bind=bind, autocommit=False, autoflush=False
        )

    def _build_history_detail(self, task: Any) -> Optional[Dict[str, Any]]:
        if not task:
            return None
        character = self.material_repo.get_by_id(task.character_id)
        chara_name = character.name if character else "未知角色"
        selected_prompts = _parse_json_list(task.selected_prompts_json)
        results = _parse_json_list(task.result_json)
        image_count = sum(
            len((r.get("generated_images") or []))
            for r in results
            if isinstance(r, dict)
        )
        return {
            "id": task.id,
            "task_id": task.id,
            "character_id": task.character_id,
            "seed_prompt": task.seed_prompt,
            "chara_name": chara_name,
            "chara_avatar": "",
            "prompt_count": len(selected_prompts),
            "image_count": image_count,
            "n": task.n,
            "aspect_ratio": task.aspect_ratio,
            "status": task.status,
            "error_message": task.error_message,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
            "selected_prompts": selected_prompts,
            "results": results,
        }

    def list_history(
        self, *, limit: int = DEFAULT_HISTORY_LIMIT, offset: int = 0
    ) -> Dict[str, Any]:
        lim = max(1, min(int(limit), 200))
        off = max(0, int(offset))
        tasks = self.quick_repo.list_history(limit=lim, offset=off)
        items: List[Dict[str, Any]] = []
        for task in tasks:
            detail = self._build_history_detail(task)
            if not detail:
                continue
            items.append(
                {
                    "id": detail["id"],
                    "task_id": detail["task_id"],
                    "character_id": detail["character_id"],
                    "seed_prompt": detail["seed_prompt"],
                    "chara_name": detail["chara_name"],
                    "chara_avatar": detail["chara_avatar"],
                    "prompt_count": detail["prompt_count"],
                    "image_count": detail["image_count"],
                    "n": detail["n"],
                    "aspect_ratio": detail["aspect_ratio"],
                    "status": detail["status"],
                    "error_message": detail["error_message"],
                    "created_at": detail["created_at"],
                    "updated_at": detail["updated_at"],
                }
            )
        return {"items": items, "total": self.quick_repo.count_history()}

    def get_history_detail(self, history_id: str) -> Optional[Dict[str, Any]]:
        hid = (history_id or "").strip()
        if not hid:
            return None
        task = self.quick_repo.get_by_id(hid)
        if not task:
            return None
        return self._build_history_detail(task)

    def get_latest_history(self) -> Optional[Dict[str, Any]]:
        task = self.quick_repo.get_latest()
        if not task:
            return None
        return self._build_history_detail(task)

    def delete_history(self, history_id: str) -> Dict[str, Any]:
        hid = (history_id or "").strip()
        if not hid:
            raise ValueError("history_id 无效")
        task = self.quick_repo.get_by_id(hid)
        if not task:
            raise ValueError("历史记录不存在")
        work_dir = task.work_dir
        deleted = self.quick_repo.delete(hid)
        if not deleted:
            raise ValueError("历史记录不存在")

        record_path = directory_service.get_quick_create_history_record_path(hid)
        try:
            if os.path.isfile(record_path):
                os.remove(record_path)
        except Exception:
            logger.warning(
                "删除一键创作历史记录文件失败: %s", record_path, exc_info=True
            )

        if work_dir:
            try:
                if os.path.isdir(work_dir):
                    shutil.rmtree(work_dir, ignore_errors=True)
            except Exception:
                logger.warning("删除一键创作工作目录失败: %s", work_dir, exc_info=True)

        tasks = self.quick_repo.list_history(limit=2000, offset=0)
        items: List[Dict[str, Any]] = []
        for t in tasks:
            c = self.material_repo.get_by_id(t.character_id)
            selected = _parse_json_list(t.selected_prompts_json)
            result_list = _parse_json_list(t.result_json)
            image_total = sum(
                len((r.get("generated_images") or []))
                for r in result_list
                if isinstance(r, dict)
            )
            items.append(
                {
                    "id": t.id,
                    "task_id": t.id,
                    "character_id": t.character_id,
                    "chara_name": c.name if c else "未知角色",
                    "chara_avatar": "",
                    "prompt_count": len(selected),
                    "image_count": image_total,
                    "n": t.n,
                    "aspect_ratio": t.aspect_ratio,
                    "status": t.status,
                    "error_message": t.error_message,
                    "created_at": _to_iso(t.created_at),
                    "updated_at": _to_iso(t.updated_at),
                }
            )
        _dump_json_atomic(
            directory_service.get_quick_create_history_index_path(),
            {
                "updated_at": datetime.now().isoformat(),
                "total": len(items),
                "items": items,
            },
        )

        latest = self.get_latest_history()
        return {"deleted_id": hid, "latest": latest}

    async def _run_task_async(self, task_id: str) -> None:
        await asyncio.to_thread(
            run_quick_create_task_sync, task_id, self._session_factory
        )

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
        seed_prompt = (latest.seed_prompt or "").strip()
        if not seed_prompt:
            raise ValueError("未找到可用的 seed_prompt，请先执行 Prompt 预生成")
        cards = json.loads(latest.result_json or "[]")
        resolved = _resolve_selected_prompts(
            selected_prompts=selected_prompts,
            latest_cards=cards if isinstance(cards, list) else [],
        )
        if not resolved:
            raise ValueError("未选择有效 Prompt")

        task = self.quick_repo.create(
            character_id=character_id,
            seed_prompt=seed_prompt,
            n=n,
            aspect_ratio=aspect_ratio,
            selected_prompts=selected_prompts,
            status="pending",
        )
        directory_service.ensure_dir_exists(task.work_dir)
        _sync_quick_create_history_files_for_task_id(self.db, task.id)

        if background_tasks:
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
            "seed_prompt": task.seed_prompt,
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
