"""
从 bio_json.official_seed_prompts 拼出供 LLM 使用的 history_seed_prompts 文本。
"""
from typing import Any, Dict, List


def _extract_texts_from_seed_rows(rows: Any) -> List[str]:
    if not isinstance(rows, list):
        return []
    out: List[str] = []
    for item in rows:
        if isinstance(item, str):
            t = item.strip()
        elif isinstance(item, dict):
            raw = item.get("text")
            t = raw.strip() if isinstance(raw, str) else ""
        else:
            t = ""
        if t:
            out.append(t)
    return out


def build_history_seed_prompts(bio: Dict[str, Any]) -> str:
    """
    合并角色专属与通用正式种子中的 text，每行一条；若无则返回固定占位。
    """
    raw = bio.get("official_seed_prompts")
    if not isinstance(raw, dict):
        return "（暂无历史正式种子提示词）"

    spec = raw.get("character_specific")
    if spec is None:
        spec = raw.get("characterSpecific")
    general = raw.get("general")

    texts = _extract_texts_from_seed_rows(spec) + _extract_texts_from_seed_rows(general)
    if not texts:
        return "（暂无历史正式种子提示词）"
    return "\n".join(f"- {t}" for t in texts)
