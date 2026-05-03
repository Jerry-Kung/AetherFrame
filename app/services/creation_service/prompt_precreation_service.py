import asyncio
import json
import logging
import os
import shutil
import time
import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.models.database import SessionLocal
from app.prompts.creation.prompt_precreation import (
    prompt_review,
    prompt_review_backup,
    prompt_step1,
    prompt_step2,
)
from app.prompts.creation.prompt_template import good_template1, init_template
from app.repositories.creation_repository import CreationPromptPrecreationRepository
from app.repositories.material_repository import MaterialCharacterRepository
from app.services import directory_service
from app.services.material_service import material_file_service
from app.tools.llm.yibu_llm_infer import yibu_gemini_infer

logger = logging.getLogger(__name__)

PREVIEW_MAX_LEN = 160
DEFAULT_HISTORY_LIMIT = 50


def _to_iso(dt: Optional[datetime]) -> str:
    if dt is None:
        return ""
    return dt.isoformat()


def _safe_load_json(path: str, default: Any) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except json.JSONDecodeError:
        return default


def _dump_json_atomic(path: str, payload: Any) -> None:
    directory_service.ensure_dir_exists(os.path.dirname(path))
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _task_cards(task: Any) -> List[Dict[str, Any]]:
    if not task or not task.result_json:
        return []
    try:
        cards = json.loads(task.result_json)
        if isinstance(cards, list):
            return cards
    except json.JSONDecodeError:
        return []
    return []


def _sync_history_files_for_task_id(db: Session, task_id: str) -> None:
    crepo = CreationPromptPrecreationRepository(db)
    mrepo = MaterialCharacterRepository(db)
    task = crepo.get_by_id(task_id)
    if not task:
        return

    history_dir = directory_service.get_prompt_precreation_history_dir()
    records_dir = directory_service.get_prompt_precreation_history_records_dir()
    directory_service.ensure_dir_exists(history_dir)
    directory_service.ensure_dir_exists(records_dir)

    character = mrepo.get_by_id(task.character_id)
    chara_name = character.name if character else "未知角色"
    cards = _task_cards(task)
    record_payload = {
        "id": task.id,
        "task_id": task.id,
        "character_id": task.character_id,
        "chara_name": chara_name,
        "chara_avatar": "",
        "seed_prompt": task.seed_prompt,
        "prompt_count": len(cards),
        "status": task.status,
        "error_message": task.error_message,
        "created_at": _to_iso(task.created_at),
        "updated_at": _to_iso(task.updated_at),
        "cards": cards,
    }
    _dump_json_atomic(
        directory_service.get_prompt_precreation_history_record_path(task.id),
        record_payload,
    )

    tasks = crepo.list_history(limit=2000, offset=0)
    items: List[Dict[str, Any]] = []
    for t in tasks:
        c = mrepo.get_by_id(t.character_id)
        cards = _task_cards(t)
        items.append(
            {
                "id": t.id,
                "task_id": t.id,
                "character_id": t.character_id,
                "chara_name": c.name if c else "未知角色",
                "chara_avatar": "",
                "seed_prompt": t.seed_prompt,
                "prompt_count": len(cards),
                "status": t.status,
                "error_message": t.error_message,
                "created_at": _to_iso(t.created_at),
                "updated_at": _to_iso(t.updated_at),
            }
        )
    _dump_json_atomic(
        directory_service.get_prompt_precreation_history_index_path(),
        {"updated_at": datetime.now().isoformat(), "total": len(items), "items": items},
    )


def resolve_chara_profile_text(
    character_id: str, bio_json: Optional[str]
) -> Optional[str]:
    md = material_file_service.read_chara_profile_markdown(
        character_id, "chara_profile_final.md"
    )
    if md and md.strip():
        return md.strip()
    try:
        bio = json.loads(bio_json or "{}")
        if isinstance(bio, dict):
            cp = bio.get("chara_profile")
            if cp is not None and str(cp).strip():
                return str(cp).strip()
    except json.JSONDecodeError:
        pass
    return None


def parse_llm_json_object(text: str) -> Dict[str, Any]:
    s = text.strip()
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


def _build_input_content(candidates: Dict[str, str]) -> str:
    keys = sorted(candidates.keys())
    items = [{k: candidates[k]} for k in keys]
    return json.dumps(items, ensure_ascii=False)


def _collect_candidates(
    *,
    chara_profile: str,
    seed_prompt: str,
    work_dir: str,
    n: int,
) -> Dict[str, str]:
    target_success = 2 * n
    max_iters = 4 * n
    candidates: Dict[str, str] = {}
    success_count = 0

    for _ in range(max_iters):
        if success_count >= target_success:
            break
        try:
            p1 = prompt_step1.format(
                chara_profile=chara_profile,
                seed_prompt=seed_prompt,
                init_template=init_template,
                good_template=good_template1,
            )
            step1_result = yibu_gemini_infer(p1, thinking_level="high", temperature=1.0)
            p2 = prompt_step2.format(
                init_template=step1_result,
                good_template=good_template1,
                chara_profile=chara_profile,
                seed_prompt=seed_prompt,
            )
            step2_result = yibu_gemini_infer(p2, thinking_level="high", temperature=1.0)
            success_count += 1
            key = f"candidate_prompt_{success_count:03d}"
            candidates[key] = step2_result
            path = os.path.join(work_dir, f"{key}.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write(step2_result)
        except Exception as e:
            logger.warning("Prompt 预生成循环跳过本次: %s", e, exc_info=True)
            continue

    if success_count < target_success:
        raise RuntimeError(
            f"备选 Prompt 仅成功生成 {success_count} 个，需要 {target_success} 个（网络或模型不稳定时可重试）"
        )
    return candidates


def _run_review(
    *,
    input_content: str,
    seed_prompt: str,
    chara_profile: str,
    n: int,
) -> str:
    def call_main() -> str:
        p = prompt_review.format(
            input_content=input_content,
            seed_prompt=seed_prompt,
            chara_profile=chara_profile,
            num_best_prompts=n,
        )
        return yibu_gemini_infer(p, thinking_level="high", temperature=0.7)

    def call_backup() -> str:
        p = prompt_review_backup.format(
            input_content=input_content,
            seed_prompt=seed_prompt,
            chara_profile=chara_profile,
            num_best_prompts=n,
        )
        return yibu_gemini_infer(p, thinking_level="high", temperature=0.7)

    for attempt in range(2):
        try:
            return call_main()
        except Exception as e:
            logger.warning(
                "审阅 LLM 调用失败 (attempt %s): %s", attempt + 1, e, exc_info=True
            )
            if attempt == 0:
                time.sleep(10)
            else:
                break
    try:
        return call_backup()
    except Exception as e2:
        logger.error("审阅备份 prompt 仍失败: %s", e2, exc_info=True)
        raise RuntimeError("审阅阶段 LLM 调用失败") from e2


def _build_cards(
    best_files: List[str], candidates: Dict[str, str]
) -> List[Dict[str, Any]]:
    today = date.today().isoformat()
    cards: List[Dict[str, Any]] = []
    for i, name in enumerate(best_files):
        body = candidates[name].strip()
        line = body.split("\n", 1)[0].strip()
        if not line:
            title = f"预生成 Prompt {i + 1}"
        elif len(line) <= 40:
            title = line
        else:
            title = line[:40] + "…"
        preview = body.replace("\n", " ")
        if len(preview) > PREVIEW_MAX_LEN:
            preview = preview[:PREVIEW_MAX_LEN] + "…"
        cards.append(
            {
                "id": str(uuid.uuid4()),
                "title": title,
                "preview": preview,
                "fullPrompt": body,
                "tags": [],
                "createdAt": today,
            }
        )
    return cards


_VALID_CHAIN_ASPECT = frozenset({"16:9", "4:3", "1:1", "3:4", "9:16"})


def _try_chain_quick_create(precreation_task_id: str) -> None:
    """预生成已成功落库后，在同一流程中可选启动一键创作（独立 DB 会话）。"""
    from app.services.creation_service.quick_create_service import QuickCreateService

    db = SessionLocal()
    try:
        prepo = CreationPromptPrecreationRepository(db)
        task = prepo.get_by_id(precreation_task_id)
        if not task or not getattr(task, "chain_quick_create", False):
            return
        n_qc = task.chain_qc_n
        aspect = (task.chain_qc_aspect_ratio or "").strip()
        max_prompts = task.chain_qc_max_prompts
        if (
            n_qc is None
            or n_qc < 1
            or n_qc > 4
            or aspect not in _VALID_CHAIN_ASPECT
            or max_prompts is None
            or max_prompts < 1
            or max_prompts > 4
        ):
            prepo.update(
                precreation_task_id,
                {"chain_error": "链式一键创作参数无效，已跳过"},
            )
            _sync_history_files_for_task_id(db, precreation_task_id)
            return
        try:
            cards = json.loads(task.result_json or "[]")
        except json.JSONDecodeError:
            cards = []
        if not isinstance(cards, list) or len(cards) == 0:
            prepo.update(
                precreation_task_id,
                {"chain_error": "无可用 Prompt 卡片，已跳过链式一键创作"},
            )
            _sync_history_files_for_task_id(db, precreation_task_id)
            return
        cap = min(len(cards), int(max_prompts))
        selected: List[Dict[str, str]] = []
        for c in cards[:cap]:
            if not isinstance(c, dict):
                continue
            pid = str(c.get("id") or "").strip()
            fp = str(c.get("fullPrompt") or "").strip()
            if pid and fp:
                selected.append({"id": pid, "fullPrompt": fp})
        if not selected:
            prepo.update(
                precreation_task_id,
                {"chain_error": "切片后无有效 Prompt，已跳过链式一键创作"},
            )
            _sync_history_files_for_task_id(db, precreation_task_id)
            return
        qc = QuickCreateService(db)
        try:
            out = qc.start_quick_create(
                character_id=task.character_id,
                selected_prompts=selected,
                n=n_qc,
                aspect_ratio=aspect,
                background_tasks=None,
            )
        except Exception as e:
            logger.error(
                "链式一键创作启动失败 precreation_task_id=%s: %s",
                precreation_task_id,
                e,
                exc_info=True,
            )
            msg = str(e) if str(e) else type(e).__name__
            prepo.update(
                precreation_task_id,
                {"chain_error": msg[:2000]},
            )
            _sync_history_files_for_task_id(db, precreation_task_id)
            return
        tid = (out or {}).get("task_id")
        if tid:
            prepo.update(
                precreation_task_id,
                {"chained_quick_create_task_id": str(tid), "chain_error": None},
            )
        _sync_history_files_for_task_id(db, precreation_task_id)
    finally:
        db.close()


def run_prompt_precreation_task_sync(task_id: str) -> None:
    db = SessionLocal()
    try:
        crepo = CreationPromptPrecreationRepository(db)
        mrepo = MaterialCharacterRepository(db)
        task = crepo.get_by_id(task_id)
        if not task:
            return
        char = mrepo.get_by_id(task.character_id)
        if not char:
            crepo.update(
                task_id,
                {
                    "status": "failed",
                    "error_message": "角色不存在",
                    "current_step": None,
                },
            )
            _sync_history_files_for_task_id(db, task_id)
            return

        chara_profile = resolve_chara_profile_text(task.character_id, char.bio_json)
        if not chara_profile:
            crepo.update(
                task_id,
                {
                    "status": "failed",
                    "error_message": "请先完成角色小档案生成后再进行 Prompt 预生成",
                    "current_step": None,
                },
            )
            _sync_history_files_for_task_id(db, task_id)
            return

        crepo.update(
            task_id,
            {"status": "running", "current_step": "collecting", "error_message": None},
        )
        _sync_history_files_for_task_id(db, task_id)
        n = task.n
        seed_prompt = task.seed_prompt
        work_dir = task.work_dir
        directory_service.ensure_dir_exists(work_dir)

        candidates = _collect_candidates(
            chara_profile=chara_profile,
            seed_prompt=seed_prompt,
            work_dir=work_dir,
            n=n,
        )

        crepo.update(task_id, {"current_step": "reviewing"})
        _sync_history_files_for_task_id(db, task_id)
        input_content = _build_input_content(candidates)
        raw = _run_review(
            input_content=input_content,
            seed_prompt=seed_prompt,
            chara_profile=chara_profile,
            n=n,
        )
        parsed = parse_llm_json_object(raw)
        best_files = parsed.get("best_prompt_files")
        if not isinstance(best_files, list):
            raise ValueError("审阅结果缺少 best_prompt_files 数组")
        best_files = [str(x) for x in best_files]
        if len(best_files) != n:
            raise ValueError(f"审阅应返回 {n} 个文件名，实际 {len(best_files)} 个")
        for name in best_files:
            if name not in candidates:
                raise ValueError(f"审阅返回了未知候选名: {name}")

        cards = _build_cards(best_files, candidates)
        crepo.update(
            task_id,
            {
                "status": "completed",
                "current_step": None,
                "error_message": None,
                "result_json": cards,
            },
        )
        _sync_history_files_for_task_id(db, task_id)
        _try_chain_quick_create(task_id)
    except Exception as e:
        logger.error("Prompt 预生成任务失败 task_id=%s: %s", task_id, e, exc_info=True)
        msg = str(e) if str(e) else type(e).__name__
        try:
            crepo = CreationPromptPrecreationRepository(db)
            if crepo.get_by_id(task_id):
                crepo.update(
                    task_id,
                    {"status": "failed", "error_message": msg, "current_step": None},
                )
                _sync_history_files_for_task_id(db, task_id)
        except Exception:
            logger.exception("写入任务失败状态时出错")
    finally:
        db.close()


class PromptPrecreationService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = CreationPromptPrecreationRepository(db)
        self.material_repo = MaterialCharacterRepository(db)

    def _parse_cards(self, task: Any) -> List[Dict[str, Any]]:
        if not task or not task.result_json:
            return []
        try:
            cards = json.loads(task.result_json)
            if isinstance(cards, list):
                return cards
        except json.JSONDecodeError:
            return []
        return []

    def _build_history_detail(self, task: Any) -> Optional[Dict[str, Any]]:
        if not task:
            return None
        character = self.material_repo.get_by_id(task.character_id)
        chara_name = character.name if character else "未知角色"
        cards = self._parse_cards(task)
        return {
            "id": task.id,
            "task_id": task.id,
            "character_id": task.character_id,
            "chara_name": chara_name,
            "chara_avatar": "",
            "seed_prompt": task.seed_prompt,
            "prompt_count": len(cards),
            "status": task.status,
            "error_message": task.error_message,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
            "cards": cards,
        }

    def _build_history_index_item(self, detail: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": detail["id"],
            "task_id": detail["task_id"],
            "character_id": detail["character_id"],
            "chara_name": detail["chara_name"],
            "chara_avatar": detail["chara_avatar"],
            "seed_prompt": detail["seed_prompt"],
            "prompt_count": detail["prompt_count"],
            "status": detail["status"],
            "error_message": detail.get("error_message"),
            "created_at": _to_iso(detail.get("created_at")),
            "updated_at": _to_iso(detail.get("updated_at")),
        }

    def _sync_history_record_file(self, task: Any) -> None:
        detail = self._build_history_detail(task)
        if not detail:
            return
        record_path = directory_service.get_prompt_precreation_history_record_path(
            task.id
        )
        record_payload = {
            **self._build_history_index_item(detail),
            "cards": detail.get("cards") or [],
        }
        _dump_json_atomic(record_path, record_payload)

    def _sync_history_index_file(self) -> None:
        tasks = self.repo.list_history(limit=2000, offset=0)
        items: List[Dict[str, Any]] = []
        for task in tasks:
            detail = self._build_history_detail(task)
            if not detail:
                continue
            items.append(self._build_history_index_item(detail))
        payload = {
            "updated_at": datetime.now().isoformat(),
            "total": len(items),
            "items": items,
        }
        index_path = directory_service.get_prompt_precreation_history_index_path()
        _dump_json_atomic(index_path, payload)

    def _sync_history_files_for_task(self, task_id: str) -> None:
        task = self.repo.get_by_id(task_id)
        if not task:
            return
        history_dir = directory_service.get_prompt_precreation_history_dir()
        records_dir = directory_service.get_prompt_precreation_history_records_dir()
        directory_service.ensure_dir_exists(history_dir)
        directory_service.ensure_dir_exists(records_dir)
        self._sync_history_record_file(task)
        self._sync_history_index_file()

    def list_history(
        self,
        *,
        limit: int = DEFAULT_HISTORY_LIMIT,
        offset: int = 0,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        lim = max(1, min(int(limit), 200))
        off = max(0, int(offset))
        st = (status or "").strip() or None
        tasks = self.repo.list_history(limit=lim, offset=off, status=st)
        items: List[Dict[str, Any]] = []
        for task in tasks:
            detail = self._build_history_detail(task)
            if not detail:
                continue
            item = self._build_history_index_item(detail)
            items.append(item)
        return {"items": items, "total": self.repo.count_history(st)}

    def get_history_detail(self, history_id: str) -> Optional[Dict[str, Any]]:
        hid = (history_id or "").strip()
        if not hid:
            return None
        task = self.repo.get_by_id(hid)
        if not task:
            return None
        return self._build_history_detail(task)

    def get_latest_history(self) -> Optional[Dict[str, Any]]:
        task = self.repo.get_latest()
        if not task:
            return None
        return self._build_history_detail(task)

    def get_latest_completed_history(self) -> Optional[Dict[str, Any]]:
        """供「一键创作」默认关联：全库最近一条已完成的任务（含 cards）。"""
        task = self.repo.get_latest_completed()
        if not task:
            return None
        return self._build_history_detail(task)

    def delete_history(self, history_id: str) -> Dict[str, Any]:
        hid = (history_id or "").strip()
        if not hid:
            raise ValueError("history_id 无效")
        task = self.repo.get_by_id(hid)
        if not task:
            raise ValueError("历史记录不存在")
        work_dir = task.work_dir
        deleted = self.repo.delete(hid)
        if not deleted:
            raise ValueError("历史记录不存在")

        record_path = directory_service.get_prompt_precreation_history_record_path(hid)
        try:
            if os.path.isfile(record_path):
                os.remove(record_path)
        except Exception:
            logger.warning("删除历史记录文件失败: %s", record_path, exc_info=True)

        if work_dir:
            try:
                if os.path.isdir(work_dir):
                    shutil.rmtree(work_dir, ignore_errors=True)
            except Exception:
                logger.warning("删除历史工作目录失败: %s", work_dir, exc_info=True)

        self._sync_history_index_file()
        latest = self.get_latest_history()
        return {"deleted_id": hid, "latest": latest}

    async def _run_task_async(self, task_id: str) -> None:
        await asyncio.to_thread(run_prompt_precreation_task_sync, task_id)

    def start_prompt_precreation(
        self,
        character_id: str,
        seed_prompt: str,
        count: int,
        background_tasks: Optional[BackgroundTasks] = None,
        chain_quick_create: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if count not in (1, 2, 3, 4):
            raise ValueError("生成数量必须为 1、2、3 或 4")
        sp = (seed_prompt or "").strip()
        if not sp:
            raise ValueError("种子提示词不能为空")

        char = self.material_repo.get_by_id(character_id)
        if not char:
            raise ValueError("角色不存在")

        chara_profile = resolve_chara_profile_text(character_id, char.bio_json)
        if not chara_profile:
            raise ValueError("请先完成角色小档案生成后再进行 Prompt 预生成")

        cq = bool(chain_quick_create)
        cn: Optional[int] = None
        car: Optional[str] = None
        cm: Optional[int] = None
        if chain_quick_create:
            cn = int(chain_quick_create["n"])
            car = str(chain_quick_create["aspect_ratio"]).strip()
            cm = int(chain_quick_create["max_prompts"])

        task = self.repo.create(
            character_id=character_id,
            seed_prompt=sp,
            n=count,
            status="pending",
            chain_quick_create=cq,
            chain_qc_n=cn,
            chain_qc_aspect_ratio=car,
            chain_qc_max_prompts=cm,
        )
        directory_service.ensure_dir_exists(task.work_dir)
        self._sync_history_files_for_task(task.id)

        if background_tasks:
            background_tasks.add_task(self._run_task_async, task.id)
        else:
            run_prompt_precreation_task_sync(task.id)

        task = self.repo.get_by_id(task.id)
        return {"task_id": task.id, "status": task.status if task else "pending"}

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        task = self.repo.get_by_id(task_id)
        if not task:
            return None
        cards = None
        if task.status == "completed" and task.result_json:
            try:
                cards = json.loads(task.result_json)
                if not isinstance(cards, list):
                    cards = None
            except json.JSONDecodeError:
                cards = None
        return {
            "task_id": task.id,
            "character_id": task.character_id,
            "status": task.status,
            "error_message": task.error_message,
            "current_step": task.current_step,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
            "cards": cards,
            "chained_quick_create_task_id": getattr(
                task, "chained_quick_create_task_id", None
            ),
            "chain_error": getattr(task, "chain_error", None),
        }
