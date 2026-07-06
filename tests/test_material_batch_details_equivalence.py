"""P1-2 等价性校验：get_characters_batch_details 批量装配 vs 单条 character_to_detail_dict。"""

import json
from datetime import datetime, timezone

from app.models.material import (
    MaterialCharacter,
    MaterialCharacterRawImage,
    MaterialCreativeDirection,
)
from app.services.material_service.material_service import MaterialService


def _make_char_with_bio(
    db,
    cid: str,
    name: str,
    *,
    bio: dict | None = None,
) -> MaterialCharacter:
    c = MaterialCharacter(
        id=cid,
        name=name,
        display_name=name,
        status="done",
        setting_text=f"setting-{cid}",
        setting_source_filename=f"{cid}.md",
        official_photos_json="[null,null,null,null,null]",
        bio_json=json.dumps(bio or {}, ensure_ascii=False),
        avatar_filename=None,
    )
    db.add(c)
    db.commit()
    return c


def _add_raw(
    db, cid: str, image_id: str, fn: str, image_type: str, tags: list, created_at=None
) -> None:
    row = MaterialCharacterRawImage(
        id=image_id,
        character_id=cid,
        stored_filename=fn,
        type=image_type,
        tags_json=json.dumps(tags, ensure_ascii=False),
    )
    if created_at is not None:
        row.created_at = created_at
    db.add(row)
    db.commit()


def _add_direction(db, did: str, cid: str, title: str, divergence: str) -> None:
    d = MaterialCreativeDirection(
        id=did,
        character_id=cid,
        title=title,
        divergence=divergence,
        description=f"desc-{did}",
    )
    db.add(d)
    db.commit()


def _bio_with_direction(direction_id: str | None) -> dict:
    return {
        "chara_profile": "profile-md",
        "official_seed_prompts": {
            "general": [
                {"id": "g1", "title": "通用1", "body": "G1"},
            ],
            "character_specific": [
                {
                    "id": "cs1",
                    "title": "专用1",
                    "body": "B1",
                    "creative_direction_id": direction_id,
                }
            ],
        },
    }


def test_batch_details_equivalence_with_single(db_session):
    """新 get_characters_batch_details 与逐条 character_to_detail_dict 应逐字段等价。"""
    db = db_session

    _make_char_with_bio(db, "char_a", "角色A", bio=_bio_with_direction("dir_a"))
    _make_char_with_bio(db, "char_b", "角色B", bio=_bio_with_direction("dir_b"))
    _make_char_with_bio(db, "char_c", "角色C", bio=_bio_with_direction(None))

    _add_direction(db, "dir_a", "char_a", "方向A", "向左")
    _add_direction(db, "dir_b", "char_b", "方向B", "向右")

    t0 = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 1, 1, 0, 1, 0, tzinfo=timezone.utc)
    _add_raw(db, "char_a", "img_a1", "a1.png", "official", ["人物"], created_at=t0)
    _add_raw(db, "char_a", "img_a2", "a2.png", "fanart", ["同人"], created_at=t1)
    _add_raw(db, "char_b", "img_b1", "b1.png", "official", [], created_at=t0)

    svc = MaterialService(db)
    ids = ["char_a", "char_b", "char_c"]

    batch = svc.get_characters_batch_details(ids)

    single = []
    for cid in ids:
        c = svc.repo.get_by_id(cid)
        single.append(svc.character_to_detail_dict(c))

    assert len(batch) == len(single)
    for b, s in zip(batch, single):
        assert set(b.keys()) == set(s.keys()), f"键集合不一致: {b.keys()} vs {s.keys()}"
        for k in b:
            assert b[k] == s[k], f"字段 {k} 不一致: {b[k]!r} vs {s[k]!r}"


def test_batch_details_empty_ids_returns_empty(db_session):
    svc = MaterialService(db_session)
    assert svc.get_characters_batch_details([]) == []


def test_batch_details_missing_character_skipped(db_session):
    """传入不存在的 id：表现与单条版一致（被 get_by_ids 过滤掉）。"""
    db = db_session
    _make_char_with_bio(db, "char_x", "角色X", bio={})
    svc = MaterialService(db)
    out = svc.get_characters_batch_details(["char_x", "missing_id"])
    assert [c["id"] for c in out] == ["char_x"]
