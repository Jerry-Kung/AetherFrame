"""为 bio.official_seed_prompts.character_specific[*] 注入 creative_direction_meta 字段."""

from typing import Any, Dict

from sqlalchemy.orm import Session

from app.models.material import MaterialCreativeDirection


def enrich_seeds_with_direction_meta(bio: Dict[str, Any], db: Session) -> Dict[str, Any]:
    """就地修改 bio dict：为 character_specific[*] 添加 creative_direction_meta 字段。"""
    if not isinstance(bio, dict):
        return bio

    seeds = bio.get("official_seed_prompts")
    if not isinstance(seeds, dict):
        return bio

    cs = seeds.get("character_specific")
    if not isinstance(cs, list):
        return bio

    dir_ids = {
        s.get("creative_direction_id")
        for s in cs
        if isinstance(s, dict) and s.get("creative_direction_id")
    }

    if not dir_ids:
        for s in cs:
            if isinstance(s, dict):
                s["creative_direction_meta"] = None
        return bio

    rows = (
        db.query(MaterialCreativeDirection)
        .filter(MaterialCreativeDirection.id.in_(dir_ids))
        .all()
    )
    dir_map = {r.id: {"title": r.title, "divergence": r.divergence} for r in rows}

    for s in cs:
        if not isinstance(s, dict):
            continue
        did = s.get("creative_direction_id")
        s["creative_direction_meta"] = dir_map.get(did) if did else None

    return bio
