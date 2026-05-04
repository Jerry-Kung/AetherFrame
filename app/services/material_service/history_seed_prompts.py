"""
从 bio_json.official_seed_prompts 拼出供 LLM 使用的 history_seed_prompts 文本。
"""
from typing import Any, Dict, List, Optional


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


def build_history_seed_prompts(
    bio: Dict[str, Any], fixed_unused_texts: Optional[List[str]] = None
) -> str:
    """
    合并角色专属、通用正式种子及（可选）未使用的全局固定模板 text，每行一条；
    若皆无则返回固定占位。
    """
    lines: List[str] = []
    raw = bio.get("official_seed_prompts") if isinstance(bio, dict) else None
    if isinstance(raw, dict):
        spec = raw.get("character_specific")
        if spec is None:
            spec = raw.get("characterSpecific")
        general = raw.get("general")
        for t in _extract_texts_from_seed_rows(spec) + _extract_texts_from_seed_rows(general):
            lines.append(f"- {t}")
    if fixed_unused_texts:
        for t in fixed_unused_texts:
            st = (t or "").strip()
            if st:
                lines.append(f"- [固定模板] {st}")
    if not lines:
        return "（暂无历史正式种子提示词）"
    return "\n".join(lines)
