"""姿势段 → LLM 姿势族标签（设计文档 §4 模块表）。本机制唯一的 LLM 调用点。

- 输入极小（姿势段约 70-150 字符），单次调用、低温、低思考层级。
- 输出必须落在 pose_taxonomy 枚举内；解析失败/越界回落 other；调用异常返回 None
  （KB 记 null 待补，不阻断构建）。
"""
import logging
import re

from experiments.feedback_kb.pose_taxonomy import PoseTaxonomy

logger = logging.getLogger(__name__)

_SYSTEM = "你是一个精确的姿势分类器。只输出一个姿势族英文标识符，不输出任何其他内容。"

_PROMPT_TEMPLATE = """以下是一段动漫角色插画 Prompt 中的姿势描述，请判断角色主体姿势属于哪个姿势族。

姿势族定义：
{families}

姿势描述：
{pose_text}

只输出一个姿势族标识符（如 sit_normal）。无法确定时输出 other。"""


def build_prompt(pose_text: str, taxonomy: PoseTaxonomy) -> str:
    families = "\n".join(f"- {name}: {desc}" for name, desc in taxonomy.families.items())
    return _PROMPT_TEMPLATE.format(families=families, pose_text=pose_text.strip())


def parse_label(response: str, taxonomy: PoseTaxonomy) -> str:
    """从模型回复里取第一个合法族名；找不到回落 other。"""
    for token in re.findall(r"[a-z_]+", response.lower()):
        if taxonomy.is_valid(token):
            return token
    logger.warning("姿势打标输出无法解析，回落 other: %r", response[:100])
    return "other"


def tag_pose(pose_text: str, taxonomy: PoseTaxonomy, infer_fn=None) -> str | None:
    """打一个姿势族标签。infer_fn 便于测试注入；默认用生产 yibu Gemini 推理。
    调用异常返回 None（待补），不抛出。"""
    if not pose_text.strip():
        return None
    if infer_fn is None:
        from app.tools.llm.yibu_llm_infer import yibu_gemini_infer

        def infer_fn(prompt):
            return yibu_gemini_infer(
                prompt=prompt, system_instruction=_SYSTEM,
                temperature=0.1, thinking_level="low",
            )
    try:
        response = infer_fn(build_prompt(pose_text, taxonomy))
    except Exception:
        logger.exception("姿势打标 LLM 调用失败，记 null 待补")
        return None
    return parse_label(response, taxonomy)
