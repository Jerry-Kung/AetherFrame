"""创意方向生成 Pipeline（单步 LLM 推理）。"""
import asyncio
import json
import logging
import os
import re
import uuid
from typing import Optional

from app.models.database import BackgroundSessionLocal
from app.models.material import (
    MaterialCreativeDirection,
    MaterialCreativeDirectionTask,
)
from app.prompts.material.creative_direction import creative_direction_prompt
from app.services.material_service import material_file_service
from app.services.material_service.history_creative_directions import (
    build_history_creative_direction_list,
)
from app.services.material_service.task_concurrency import get_global_llm_semaphore
from app.tools.llm.yibu_llm_infer import yibu_gemini_infer

logger = logging.getLogger(__name__)

_DIVERGENCE_LABEL_FOR_PROMPT = {"low": "低", "mid": "中", "high": "高"}


def _strip_json_fence(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    return s.strip()


def _parse_direction_json(raw: str) -> tuple[str, str, Optional[list[str]]]:
    cleaned = _strip_json_fence(raw)
    try:
        obj = json.loads(cleaned)
    except json.JSONDecodeError as e:
        snippet = (cleaned[:800] + "..." if len(cleaned) > 800 else cleaned)
        raise ValueError(f"LLM JSON parse failed: {e}; snippet={snippet!r}") from e
    title = obj.get("title")
    desc = obj.get("description")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("LLM output missing 'title'")
    if not isinstance(desc, str) or not desc.strip():
        raise ValueError("LLM output missing 'description'")
    raw_home = obj.get("home_settings")
    home: Optional[list[str]] = None
    if isinstance(raw_home, list):
        seen: set[str] = set()
        cleaned_home: list[str] = []
        for x in raw_home:
            if not isinstance(x, str):
                continue
            s = x.strip()
            if not s or s in seen:
                continue
            seen.add(s)
            cleaned_home.append(s)
            if len(cleaned_home) >= 3:
                break
        home = cleaned_home or None
    return title.strip(), desc, home


def _resolve_chara_profile_text(character_id: str) -> str:
    text = material_file_service.read_chara_profile_markdown(
        character_id, "chara_profile_final.md"
    )
    if not text or not text.strip():
        raise FileNotFoundError(
            f"chara_profile_final.md not found for character {character_id}"
        )
    return text


def _write_direction_json_file(character_id: str, direction: MaterialCreativeDirection) -> None:
    dir_path = os.path.join(
        material_file_service.get_character_dir(character_id), "creative_directions"
    )
    os.makedirs(dir_path, exist_ok=True)
    file_path = os.path.join(dir_path, f"{direction.id}.json")
    home_settings_val: Optional[list[str]] = None
    if direction.home_settings:
        try:
            parsed = json.loads(direction.home_settings)
            if isinstance(parsed, list):
                home_settings_val = [x for x in parsed if isinstance(x, str)]
        except json.JSONDecodeError:
            home_settings_val = None
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "id": direction.id,
                    "title": direction.title,
                    "description": direction.description,
                    "home_settings": home_settings_val,
                    "divergence": direction.divergence,
                    "initial_input": direction.initial_input,
                    "created_at": (
                        direction.created_at.isoformat() if direction.created_at else None
                    ),
                    "updated_at": (
                        direction.updated_at.isoformat() if direction.updated_at else None
                    ),
                },
                f,
                ensure_ascii=False,
                indent=2,
            )
    except Exception as e:
        logger.warning("failed to write direction file %s: %s", file_path, e)


async def run_creative_direction_task(task_id: str) -> None:
    """BackgroundTasks 入口。"""
    semaphore = get_global_llm_semaphore()

    with BackgroundSessionLocal() as db:
        task = db.get(MaterialCreativeDirectionTask, task_id)
        if task is None:
            logger.error("task %s not found, abort", task_id)
            return
        task.status = "processing"
        task.current_step = "generating"
        character_id = task.character_id
        divergence = task.divergence
        initial_input = task.initial_input or ""
        db.commit()

    async with semaphore:
        try:
            with BackgroundSessionLocal() as db:
                chara_profile = _resolve_chara_profile_text(character_id)
                history_text = build_history_creative_direction_list(db, character_id)

            prompt = creative_direction_prompt.format(
                chara_profile=chara_profile,
                input_content=initial_input.strip() or "（无）",
                divergence=_DIVERGENCE_LABEL_FOR_PROMPT[divergence],
                history_creative_direction_list=history_text,
            )

            llm_raw = await asyncio.to_thread(
                yibu_gemini_infer,
                prompt,
                thinking_level="high",
                temperature=1.0,
            )
            title, description, home_settings = _parse_direction_json(llm_raw)

            with BackgroundSessionLocal() as db:
                direction = MaterialCreativeDirection(
                    id=str(uuid.uuid4()),
                    character_id=character_id,
                    title=title,
                    description=description,
                    divergence=divergence,
                    initial_input=initial_input or None,
                    source_task_id=task_id,
                    home_settings=(
                        json.dumps(home_settings, ensure_ascii=False)
                        if home_settings else None
                    ),
                )
                db.add(direction)
                db.flush()

                task = db.get(MaterialCreativeDirectionTask, task_id)
                task.status = "completed"
                task.current_step = "done"
                task.result_direction_id = direction.id
                db.commit()
                db.refresh(direction)

            try:
                _write_direction_json_file(character_id, direction)
            except Exception as e:
                logger.warning(
                    "failed to write direction file after task %s completed: %s",
                    task_id,
                    e,
                )
            logger.info("direction task %s completed → direction %s", task_id, direction.id)

        except Exception as e:
            logger.exception("direction task %s failed: %s", task_id, e)
            with BackgroundSessionLocal() as db:
                task = db.get(MaterialCreativeDirectionTask, task_id)
                if task is not None:
                    task.status = "failed"
                    task.error_message = str(e)[:2000]
                    db.commit()
