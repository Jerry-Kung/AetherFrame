"""
生成创作建议：读四份角色小档案 Markdown，两次 Gemini 推理，落盘 md 与种子草稿 JSON。
"""
import json
import logging
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.prompts.material.creation_advice import creation_advice_prompt, creation_seed_prompt
from app.services.material_service import material_file_service
from app.services.material_service.history_seed_prompts import build_history_seed_prompts
from app.tools.llm.yibu_llm_infer import yibu_gemini_infer

logger = logging.getLogger(__name__)

STEP_CREATION_ADVICE = "creation_advice"
STEP_CREATION_SEED = "creation_seed"

OnStep = Optional[Callable[[str], None]]


def _strip_json_fence(text: str) -> str:
    s = text.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.IGNORECASE)
        s = re.sub(r"\s*```\s*$", "", s)
    return s.strip()


def parse_seed_prompt_llm_json(text: str) -> Dict[str, List[str]]:
    """解析种子提示词 LLM 输出为 character_specific / general 字符串列表。"""
    raw_s = _strip_json_fence(text)
    data = json.loads(raw_s)
    if not isinstance(data, dict):
        raise ValueError("JSON 根节点须为对象")

    def as_str_list(key: str) -> List[str]:
        v = data.get(key)
        if v is None:
            return []
        if not isinstance(v, list):
            raise ValueError(f"{key} 须为数组")
        out: List[str] = []
        for x in v:
            if not isinstance(x, str):
                raise ValueError(f"{key} 中每项须为字符串")
            t = x.strip()
            if t:
                out.append(t)
        return out

    return {
        "character_specific": as_str_list("character_specific"),
        "general": as_str_list("general"),
    }


def load_chara_profile_prerequisite_contents(character_id: str) -> Tuple[str, str, str, str]:
    """读取四份前置 Markdown；调用方已保证文件存在。"""
    tu = material_file_service.read_chara_profile_markdown(character_id, "text_understanding.md")
    vo = material_file_service.read_chara_profile_markdown(
        character_id, "visual_understanding_official.md"
    )
    vf = material_file_service.read_chara_profile_markdown(
        character_id, "visual_understanding_fanart.md"
    )
    cp = material_file_service.read_chara_profile_markdown(character_id, "chara_profile_final.md")
    if tu is None or vo is None or vf is None or cp is None:
        raise FileNotFoundError("角色小档案前置文件不完整")
    return tu, vo, vf, cp


def run_creation_advice_pipeline(
    character_id: str,
    bio: Dict[str, Any],
    on_step: OnStep = None,
    fixed_unused_texts: Optional[List[str]] = None,
) -> Tuple[str, Dict[str, List[str]]]:
    """
    执行两次推理，写入 creation_advice.md 与 creation_seed_draft.json。
    返回 (创作建议 Markdown, 种子草稿 dict)。
    """
    text_understanding, visual_official, visual_fanart, chara_profile = (
        load_chara_profile_prerequisite_contents(character_id)
    )
    history_seed_prompts = build_history_seed_prompts(bio, fixed_unused_texts)

    if on_step:
        on_step(STEP_CREATION_ADVICE)
    prompt_a = creation_advice_prompt.format(
        text_understanding=text_understanding,
        visual_understand_official_result=visual_official,
        visual_understand_fanart_result=visual_fanart,
        chara_profile=chara_profile,
    )
    advice_md = yibu_gemini_infer(prompt_a, thinking_level="high", temperature=1.0)
    material_file_service.write_creation_advice_markdown(character_id, advice_md)

    if on_step:
        on_step(STEP_CREATION_SEED)
    prompt_s = creation_seed_prompt.format(
        text_understanding=text_understanding,
        visual_understand_official_result=visual_official,
        visual_understand_fanart_result=visual_fanart,
        chara_profile=chara_profile,
        history_seed_prompts=history_seed_prompts,
    )
    raw_seed = yibu_gemini_infer(prompt_s, thinking_level="high", temperature=1.0)
    try:
        seed_draft = parse_seed_prompt_llm_json(raw_seed)
    except (json.JSONDecodeError, ValueError) as e:
        snippet = raw_seed[:800] if isinstance(raw_seed, str) else ""
        raise ValueError(f"种子提示词 JSON 解析失败: {e}; 响应片段: {snippet!r}") from e

    material_file_service.write_creation_seed_draft_json(character_id, seed_draft)
    return advice_md, seed_draft
