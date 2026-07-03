"""种子提示词生成 Pipeline（单步 LLM 推理）。"""
import asyncio
import json
import logging
import os
import re
from typing import Any, Dict, Optional

from app.models.database import BackgroundSessionLocal
from app.models.material import (
    MaterialCharacter,
    MaterialCreativeDirection,
    MaterialSeedPromptTask,
)
from app.prompts.material.creative_direction import creation_direction_seed_prompt
from app.services.creation_service.composition_dimensions import (
    get_dimension_values,
    get_home_setting_pose_hints,
)
from app.services.material_service import material_file_service
from app.services.material_service.history_seed_prompts import build_history_seed_prompts
from app.services.material_service.task_concurrency import get_global_llm_semaphore
from app.tools.llm.yibu_llm_infer import yibu_gemini_infer

logger = logging.getLogger(__name__)

FALLBACK_DIRECTION_TEXT = (
    "用户未指定创意方向，请基于角色的原始默认世界观创作种子提示词"
)

_SEED_HOME_SETTINGS_FALLBACK = (
    "本方向未提供 home_settings 候选列表，请自由选择自然的居家背景"
    "（如客厅沙发、卧室大床、书房地毯等），并让所有种子分布在你选定的 1–3 个背景之间。"
)


def _strip_json_fence(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    return s.strip()


def _parse_seed_draft_json(raw: str) -> list[str]:
    cleaned = _strip_json_fence(raw)
    try:
        obj = json.loads(cleaned)
    except json.JSONDecodeError as e:
        snippet = cleaned[:800] + "..." if len(cleaned) > 800 else cleaned
        raise ValueError(f"LLM JSON parse failed: {e}; snippet={snippet!r}") from e
    items = obj.get("character_specific")
    if not isinstance(items, list):
        raise ValueError("LLM output missing 'character_specific' list")
    out: list[str] = []
    for x in items:
        if isinstance(x, str) and x.strip():
            out.append(x.strip())
    if not out:
        raise ValueError("LLM output 'character_specific' is empty after filtering")
    return out


def _resolve_chara_profile_text(character_id: str) -> str:
    text = material_file_service.read_chara_profile_markdown(
        character_id, "chara_profile_final.md"
    )
    if not text or not text.strip():
        raise FileNotFoundError(
            f"chara_profile_final.md not found for character {character_id}"
        )
    return text


def _render_pose_family_enum() -> str:
    return "\n".join(
        f"  - `{v.code}` ({v.display_name}): {v.description}"
        for v in get_dimension_values("pose_family")
    )


def _render_home_setting_hints() -> str:
    lines = []
    for setting, poses in get_home_setting_pose_hints():
        lines.append(f"  - {setting} → {' / '.join(poses)}")
    return "\n".join(lines)


def _fold_home_settings_into_direction_text(
    *, title: str, description: str, home_settings: Optional[list[str]]
) -> str:
    if not home_settings:
        return f"{title}\n\n{description}"
    hs_line = "home_settings（候选居家背景框架）: " + " / ".join(home_settings)
    return f"{title}\n\n{description}\n\n{hs_line}"


def _build_seed_prompt(
    *,
    chara_profile: str,
    direction_text: str,
    history_seed_prompts: str,
    has_home_settings: bool = True,
) -> str:
    home_setting_source = (
        "" if has_home_settings else _SEED_HOME_SETTINGS_FALLBACK
    )
    return creation_direction_seed_prompt.format(
        chara_profile=chara_profile,
        chara_creative_direction=direction_text,
        history_seed_prompts=history_seed_prompts,
        pose_family_enum=_render_pose_family_enum(),
        home_setting_hint_table=_render_home_setting_hints(),
        home_settings_fallback_note=home_setting_source,
        pose_family_distribution_bias="",
    )


def _resolve_direction_text(
    db, character_id: str, creative_direction_id: Optional[str]
) -> tuple[str, Optional[str], Optional[list[str]]]:
    """返回 (注入文本, 实际生效的方向 id, home_settings 列表)。方向不存在 / 跨角色时降级为兜底文案。"""
    if not creative_direction_id:
        return FALLBACK_DIRECTION_TEXT, None, None
    row = db.get(MaterialCreativeDirection, creative_direction_id)
    if row is None or row.character_id != character_id:
        logger.warning(
            "seed task: direction %s invalid (deleted or cross-character); falling back",
            creative_direction_id,
        )
        return FALLBACK_DIRECTION_TEXT, None, None
    home_list: Optional[list[str]] = None
    if row.home_settings:
        try:
            parsed = json.loads(row.home_settings)
            if isinstance(parsed, list):
                home_list = [
                    str(x) for x in parsed if isinstance(x, str) and x.strip()
                ]
                if not home_list:
                    home_list = None
        except json.JSONDecodeError:
            home_list = None
    folded = _fold_home_settings_into_direction_text(
        title=row.title, description=row.description, home_settings=home_list
    )
    return folded, creative_direction_id, home_list


def _write_seed_draft_file(
    character_id: str, task_id: str, items: list[str]
) -> bool:
    """落盘 data/material/characters/<id>/seed_prompt_tasks/<task_id>/seed_draft.json。"""
    char_dir = material_file_service.get_character_dir(character_id)
    task_dir = os.path.join(char_dir, "seed_prompt_tasks", task_id)
    os.makedirs(task_dir, exist_ok=True)
    file_path = os.path.join(task_dir, "seed_draft.json")
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump({"character_specific": items}, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.warning("failed to write seed_draft.json (task %s): %s", task_id, e)
        return False


async def run_seed_prompt_task(task_id: str) -> None:
    """BackgroundTasks 入口。"""
    semaphore = get_global_llm_semaphore()

    with BackgroundSessionLocal() as db:
        task = db.get(MaterialSeedPromptTask, task_id)
        if task is None:
            logger.error("seed task %s not found, abort", task_id)
            return
        task.status = "processing"
        task.current_step = "generating"
        character_id = task.character_id
        requested_direction_id = task.creative_direction_id
        db.commit()

    async with semaphore:
        try:
            with BackgroundSessionLocal() as db:
                chara_profile = _resolve_chara_profile_text(character_id)
                direction_text, effective_direction_id, home_list = _resolve_direction_text(
                    db, character_id, requested_direction_id
                )
                char_row = db.get(MaterialCharacter, character_id)
                bio = {}
                if char_row is not None and char_row.bio_json:
                    try:
                        bio = json.loads(char_row.bio_json)
                    except json.JSONDecodeError:
                        bio = {}
                history_text = build_history_seed_prompts(
                    bio, creative_direction_id=effective_direction_id
                )

            prompt = _build_seed_prompt(
                chara_profile=chara_profile,
                direction_text=direction_text,
                history_seed_prompts=history_text,
                has_home_settings=bool(home_list),
            )

            llm_raw = await asyncio.to_thread(
                yibu_gemini_infer,
                prompt,
                thinking_level="high",
                temperature=1.0,
            )
            items = _parse_seed_draft_json(llm_raw)

            if not _write_seed_draft_file(character_id, task_id, items):
                raise RuntimeError(f"failed to write seed_draft.json for task {task_id}")

            with BackgroundSessionLocal() as db:
                task = db.get(MaterialSeedPromptTask, task_id)
                task.status = "completed"
                task.current_step = "done"
                db.commit()

            logger.info(
                "seed task %s completed (%d items, direction=%s)",
                task_id,
                len(items),
                effective_direction_id,
            )

        except Exception as e:
            logger.exception("seed task %s failed: %s", task_id, e)
            with BackgroundSessionLocal() as db:
                task = db.get(MaterialSeedPromptTask, task_id)
                if task is not None:
                    task.status = "failed"
                    task.error_message = str(e)[:2000]
                    db.commit()


def read_seed_draft_file(character_id: str, task_id: str) -> Optional[Dict[str, Any]]:
    """供路由层 status 端点读取草稿内容。"""
    char_dir = material_file_service.get_character_dir(character_id)
    file_path = os.path.join(char_dir, "seed_prompt_tasks", task_id, "seed_draft.json")
    if not os.path.exists(file_path):
        return None
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("failed to read seed_draft.json (task %s): %s", task_id, e)
        return None
