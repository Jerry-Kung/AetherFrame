import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy import event

from app.models.material import MaterialCreativeDirection, MaterialCharacter
from app.services.material_service.seed_meta_enrichment import enrich_seeds_with_direction_meta


def _make_character(db_session) -> MaterialCharacter:
    char_id = f"mchar_{uuid.uuid4().hex[:10]}"
    row = MaterialCharacter(
        id=char_id,
        name="Test",
        display_name="Test",
        status="idle",
        setting_text="",
    )
    db_session.add(row)
    db_session.commit()
    return row


def test_enrich_no_seeds(db_session):
    bio = {"chara_profile": "x"}
    out = enrich_seeds_with_direction_meta(bio, db_session)
    assert out is bio


def test_enrich_empty_cs(db_session):
    bio = {"official_seed_prompts": {"character_specific": [], "general": []}}
    out = enrich_seeds_with_direction_meta(bio, db_session)
    assert out["official_seed_prompts"]["character_specific"] == []


def test_enrich_no_direction_ids(db_session):
    bio = {
        "official_seed_prompts": {
            "character_specific": [
                {"id": "1", "text": "a", "used": False, "creative_direction_id": None}
            ],
            "general": [],
        }
    }
    enrich_seeds_with_direction_meta(bio, db_session)
    assert bio["official_seed_prompts"]["character_specific"][0]["creative_direction_meta"] is None


def test_enrich_single_direction(db_session):
    char = _make_character(db_session)
    dir_id = str(uuid.uuid4())
    db_session.add(
        MaterialCreativeDirection(
            id=dir_id,
            character_id=char.id,
            title="同向",
            description="x",
            divergence="low",
        )
    )
    db_session.commit()
    bio = {
        "official_seed_prompts": {
            "character_specific": [
                {"id": "1", "text": "a", "creative_direction_id": dir_id},
                {"id": "2", "text": "b", "creative_direction_id": dir_id},
                {"id": "3", "text": "c", "creative_direction_id": dir_id},
                {"id": "4", "text": "d", "creative_direction_id": dir_id},
                {"id": "5", "text": "e", "creative_direction_id": dir_id},
            ],
            "general": [],
        }
    }
    enrich_seeds_with_direction_meta(bio, db_session)
    cs = bio["official_seed_prompts"]["character_specific"]
    assert all(m["title"] == "同向" and m["divergence"] == "low" for m in (x["creative_direction_meta"] for x in cs))


def test_enrich_multiple_directions(db_session):
    char = _make_character(db_session)
    ids = [str(uuid.uuid4()) for _ in range(3)]
    for i, did in enumerate(ids):
        db_session.add(
            MaterialCreativeDirection(
                id=did,
                character_id=char.id,
                title=f"T{i}",
                description="x",
                divergence=["low", "mid", "high"][i],
            )
        )
    db_session.commit()
    bio = {
        "official_seed_prompts": {
            "character_specific": [
                {"id": "1", "creative_direction_id": ids[0]},
                {"id": "2", "creative_direction_id": ids[1]},
                {"id": "3", "creative_direction_id": ids[2]},
            ],
            "general": [],
        }
    }
    enrich_seeds_with_direction_meta(bio, db_session)
    cs = bio["official_seed_prompts"]["character_specific"]
    assert cs[0]["creative_direction_meta"]["title"] == "T0"
    assert cs[1]["creative_direction_meta"]["divergence"] == "mid"
    assert cs[2]["creative_direction_meta"]["title"] == "T2"


def test_enrich_with_null_direction_id_mixed(db_session):
    char = _make_character(db_session)
    dir_id = str(uuid.uuid4())
    db_session.add(
        MaterialCreativeDirection(
            id=dir_id,
            character_id=char.id,
            title="有",
            description="x",
            divergence="high",
        )
    )
    db_session.commit()
    bio = {
        "official_seed_prompts": {
            "character_specific": [
                {"id": "1", "creative_direction_id": dir_id},
                {"id": "2", "creative_direction_id": None},
            ],
            "general": [],
        }
    }
    enrich_seeds_with_direction_meta(bio, db_session)
    cs = bio["official_seed_prompts"]["character_specific"]
    assert cs[0]["creative_direction_meta"] is not None
    assert cs[1]["creative_direction_meta"] is None


def test_enrich_with_deleted_direction(db_session):
    bio = {
        "official_seed_prompts": {
            "character_specific": [{"id": "1", "creative_direction_id": "gone-id"}],
            "general": [],
        }
    }
    enrich_seeds_with_direction_meta(bio, db_session)
    assert bio["official_seed_prompts"]["character_specific"][0]["creative_direction_meta"] is None


def test_enrich_query_count_le_1(db_session):
    char = _make_character(db_session)
    dir_id = str(uuid.uuid4())
    db_session.add(
        MaterialCreativeDirection(
            id=dir_id,
            character_id=char.id,
            title="Q",
            description="x",
            divergence="low",
        )
    )
    db_session.commit()
    bio = {
        "official_seed_prompts": {
            "character_specific": [
                {"id": str(i), "creative_direction_id": dir_id} for i in range(5)
            ],
            "general": [],
        }
    }
    counts: list[int] = []

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        if "material_creative_directions" in str(statement).lower():
            counts.append(1)

    event.listen(db_session.bind, "before_cursor_execute", before_cursor_execute)
    try:
        enrich_seeds_with_direction_meta(bio, db_session)
    finally:
        event.remove(db_session.bind, "before_cursor_execute", before_cursor_execute)
    assert len(counts) <= 1


def test_enrich_does_not_touch_general(db_session):
    bio = {
        "official_seed_prompts": {
            "character_specific": [],
            "general": [{"id": "g1", "text": "legacy"}],
        }
    }
    enrich_seeds_with_direction_meta(bio, db_session)
    assert "creative_direction_meta" not in bio["official_seed_prompts"]["general"][0]
