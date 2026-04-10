import asyncio
import json
import logging
import os
import time
import uuid
from datetime import date
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


def resolve_chara_profile_text(character_id: str, bio_json: Optional[str]) -> Optional[str]:
    md = material_file_service.read_chara_profile_markdown(character_id, "chara_profile_final.md")
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
            logger.warning("审阅 LLM 调用失败 (attempt %s): %s", attempt + 1, e, exc_info=True)
            if attempt == 0:
                time.sleep(10)
            else:
                break
    try:
        return call_backup()
    except Exception as e2:
        logger.error("审阅备份 prompt 仍失败: %s", e2, exc_info=True)
        raise RuntimeError("审阅阶段 LLM 调用失败") from e2


def _build_cards(best_files: List[str], candidates: Dict[str, str]) -> List[Dict[str, Any]]:
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
                {"status": "failed", "error_message": "角色不存在", "current_step": None},
            )
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
            return

        crepo.update(task_id, {"status": "running", "current_step": "collecting", "error_message": None})
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
        except Exception:
            logger.exception("写入任务失败状态时出错")
    finally:
        db.close()


class PromptPrecreationService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = CreationPromptPrecreationRepository(db)
        self.material_repo = MaterialCharacterRepository(db)

    async def _run_task_async(self, task_id: str) -> None:
        await asyncio.to_thread(run_prompt_precreation_task_sync, task_id)

    def start_prompt_precreation(
        self,
        character_id: str,
        seed_prompt: str,
        count: int,
        background_tasks: Optional[BackgroundTasks] = None,
    ) -> Dict[str, Any]:
        if count not in (2, 3, 4):
            raise ValueError("生成数量必须为 2、3 或 4")
        sp = (seed_prompt or "").strip()
        if not sp:
            raise ValueError("种子提示词不能为空")

        char = self.material_repo.get_by_id(character_id)
        if not char:
            raise ValueError("角色不存在")

        chara_profile = resolve_chara_profile_text(character_id, char.bio_json)
        if not chara_profile:
            raise ValueError("请先完成角色小档案生成后再进行 Prompt 预生成")

        task = self.repo.create(
            character_id=character_id,
            seed_prompt=sp,
            n=count,
            status="pending",
        )
        directory_service.ensure_dir_exists(task.work_dir)

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
        }
