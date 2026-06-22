"""为 bio.official_seed_prompts.character_specific[*] 注入 creative_direction_meta 字段."""

from typing import Any, Dict, Iterable, Set

from sqlalchemy.orm import Session

from app.models.material import MaterialCreativeDirection


def collect_direction_ids_from_bio(bio: Any) -> Set[str]:
    """从 bio 中提取所有引用到的 creative_direction_id，供上层一次性批量预查。"""
    if not isinstance(bio, dict):
        return set()
    seeds = bio.get("official_seed_prompts")
    if not isinstance(seeds, dict):
        return set()
    cs = seeds.get("character_specific")
    if not isinstance(cs, list):
        return set()
    return {
        s.get("creative_direction_id")
        for s in cs
        if isinstance(s, dict) and s.get("creative_direction_id")
    }


def fetch_direction_meta_map(
    db: Session, direction_ids: Iterable[str]
) -> Dict[str, Dict[str, Any]]:
    """一次性按 ID 批量拉 creative_direction，返回 {id: {title, divergence}}。"""
    ids = list({i for i in direction_ids if i})
    if not ids:
        return {}
    rows = (
        db.query(MaterialCreativeDirection)
        .filter(MaterialCreativeDirection.id.in_(ids))
        .all()
    )
    return {r.id: {"title": r.title, "divergence": r.divergence} for r in rows}


def enrich_seeds_with_direction_meta_from_map(
    bio: Dict[str, Any], dir_map: Dict[str, Dict[str, Any]]
) -> Dict[str, Any]:
    """就地修改 bio：用已查好的 dir_map 为 character_specific[*] 填 creative_direction_meta。"""
    if not isinstance(bio, dict):
        return bio
    seeds = bio.get("official_seed_prompts")
    if not isinstance(seeds, dict):
        return bio
    cs = seeds.get("character_specific")
    if not isinstance(cs, list):
        return bio
    for s in cs:
        if not isinstance(s, dict):
            continue
        did = s.get("creative_direction_id")
        s["creative_direction_meta"] = dir_map.get(did) if did else None
    return bio


def enrich_seeds_with_direction_meta(bio: Dict[str, Any], db: Session) -> Dict[str, Any]:
    """就地修改 bio dict：为 character_specific[*] 添加 creative_direction_meta 字段。
    单角色入口；批量场景请用 collect_direction_ids_from_bio + fetch_direction_meta_map +
    enrich_seeds_with_direction_meta_from_map。
    """
    if not isinstance(bio, dict):
        return bio
    dir_ids = collect_direction_ids_from_bio(bio)
    dir_map = fetch_direction_meta_map(db, dir_ids) if dir_ids else {}
    return enrich_seeds_with_direction_meta_from_map(bio, dir_map)
