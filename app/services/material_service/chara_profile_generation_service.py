"""
角色小档案生成：四步 LLM 流水线，Markdown 落盘。
"""
import logging
from typing import Callable, List, Optional

from app.prompts.material.chara_profile import (
    text_integration_prompt,
    text_understanding_prompt,
    visual_understand_fanart_prompt,
    visual_understand_official_prompt,
)
from app.services.material_service import material_file_service
from app.tools.llm.yibu_llm_infer import yibu_gemini_infer

logger = logging.getLogger(__name__)

STEP_TEXT = "text_understanding"
STEP_VISUAL_OFFICIAL = "visual_official"
STEP_VISUAL_FANART = "visual_fanart"
STEP_INTEGRATION = "text_integration"

OnStep = Optional[Callable[[str], None]]


def run_chara_profile_pipeline(
    character_id: str,
    persona_text: str,
    official_image_list: List[str],
    fanart_image_list: List[str],
    on_step: OnStep = None,
) -> str:
    """
    按顺序执行四步推理并写入 chara_profile 目录下四个 md。
    返回最终 Markdown 正文（与 chara_profile_final.md 一致）。
    """
    if on_step:
        on_step(STEP_TEXT)
    prompt_t = text_understanding_prompt.format(persona_text=persona_text)
    text_understanding = yibu_gemini_infer(prompt_t, thinking_level="high")
    material_file_service.write_chara_profile_markdown(
        character_id, "text_understanding.md", text_understanding
    )

    if on_step:
        on_step(STEP_VISUAL_OFFICIAL)
    visual_official = yibu_gemini_infer(
        visual_understand_official_prompt,
        image_path=official_image_list,
        thinking_level="high",
    )
    material_file_service.write_chara_profile_markdown(
        character_id, "visual_understanding_official.md", visual_official
    )

    if on_step:
        on_step(STEP_VISUAL_FANART)
    prompt_f = visual_understand_fanart_prompt.format(
        visual_understand_official_result=visual_official
    )
    visual_fanart = yibu_gemini_infer(
        prompt_f,
        image_path=fanart_image_list,
        thinking_level="high",
    )
    material_file_service.write_chara_profile_markdown(
        character_id, "visual_understanding_fanart.md", visual_fanart
    )

    if on_step:
        on_step(STEP_INTEGRATION)
    prompt_i = text_integration_prompt.format(
        text_understanding=text_understanding,
        visual_understand_official_result=visual_official,
        visual_understand_fanart_result=visual_fanart,
    )
    final_md = yibu_gemini_infer(prompt_i, thinking_level="high")
    material_file_service.write_chara_profile_markdown(
        character_id, "chara_profile_final.md", final_md
    )
    return final_md
