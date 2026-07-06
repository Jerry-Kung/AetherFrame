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


def _extract_text_one(entry) -> str:
    if isinstance(entry, str):
        return entry.strip()
    if isinstance(entry, dict):
        raw = entry.get("text")
        return raw.strip() if isinstance(raw, str) else ""
    return ""


def build_history_seed_prompts(
    bio: Dict[str, Any],
    creative_direction_id: Optional[str] = None,
    fixed_unused_texts: Optional[List[str]] = None,
) -> str:
    """
    构建喂给 LLM 的「历史种子提示词黑名单」文本。

    作用域规则（design.md §4.4）：
    - creative_direction_id is None（默认世界观）:
        包含 character_specific 中 creative_direction_id ∈ {None, 缺失字段} 的条目
        + 全部 general[] 条目（遗留兼容）
    - creative_direction_id == "<id>":
        仅包含 character_specific 中 creative_direction_id == <id> 的条目
        （不含 general[]、不含其他方向）

    fixed_unused_texts 参数保留用于向后兼容（旧 creation_advice service）；
    新 seed_prompt_generation_service **不传**该参数。

    空集时返回字面文案「（暂无历史种子提示词）」。
    """
    # 向后兼容：旧调用方把 fixed_unused_texts 作为第 2 个位置参数传入
    if isinstance(creative_direction_id, list):
        fixed_unused_texts = creative_direction_id
        creative_direction_id = None
    raw = bio.get("official_seed_prompts") if isinstance(bio, dict) else None
    if not isinstance(raw, dict):
        char_spec_rows = []
        general_rows = []
    else:
        cs_raw = raw.get("character_specific") or raw.get("characterSpecific") or []
        char_spec_rows = cs_raw if isinstance(cs_raw, list) else []
        general_raw = raw.get("general") or []
        general_rows = general_raw if isinstance(general_raw, list) else []

    lines: list[str] = []

    if creative_direction_id is None:
        for entry in char_spec_rows:
            if isinstance(entry, dict):
                dir_id = entry.get("creative_direction_id")
                if dir_id is None:
                    t = (entry.get("text") or "").strip()
                    if t:
                        lines.append(f"- {t}")
        for entry in general_rows:
            t = _extract_text_one(entry)
            if t:
                lines.append(f"- {t}")
    else:
        for entry in char_spec_rows:
            if isinstance(entry, dict) and entry.get("creative_direction_id") == creative_direction_id:
                t = (entry.get("text") or "").strip()
                if t:
                    lines.append(f"- {t}")

    if fixed_unused_texts:
        for t in fixed_unused_texts:
            if isinstance(t, str) and t.strip():
                lines.append(f"- [固定模板] {t.strip()}")

    if not lines:
        return "（暂无历史种子提示词）"
    return "\n".join(lines)
