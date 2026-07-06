"""组装喂给 LLM 的「历史创意方向黑名单」文本。"""
import re

from sqlalchemy.orm import Session

from app.models.material import MaterialCreativeDirection

_DIVERGENCE_LABEL = {"low": "低", "mid": "中", "high": "高"}


def _extract_core_topic_first_sentence(markdown: str) -> str:
    """从结构化 markdown 中抽取「核心主题」段落首句。"""
    m = re.search(r"##\s*核心主题\s*\n+([^\n#]+)", markdown)
    if m:
        return m.group(1).strip()[:80]
    return re.sub(r"\s+", " ", markdown).strip()[:80]


def build_history_creative_direction_list(db: Session, character_id: str) -> str:
    """返回填入 Prompt `{history_creative_direction_list}` 槽位的字符串。"""
    rows = (
        db.query(MaterialCreativeDirection)
        .filter_by(character_id=character_id)
        .order_by(MaterialCreativeDirection.created_at.desc())
        .all()
    )
    if not rows:
        return "（暂无历史创意主题）"

    lines = []
    for r in rows:
        label = _DIVERGENCE_LABEL.get(r.divergence, r.divergence)
        topic = _extract_core_topic_first_sentence(r.description or "")
        lines.append(f"- 【{label}】{r.title}：{topic}")
    return "\n".join(lines)
