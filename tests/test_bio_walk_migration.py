import json
import uuid

import pytest
from sqlalchemy import text

from app.models.database import (
    _BIO_WALK_FLAG,
    migrate_bio_official_seed_prompts_add_direction_fk,
    engine,
    _ensure_app_migrations_table,
)
from app.models.material import MaterialCharacter


def _make_character(db_session, bio: dict) -> MaterialCharacter:
    char_id = f"mchar_{uuid.uuid4().hex[:10]}"
    row = MaterialCharacter(
        id=char_id,
        name="Test",
        display_name="Test",
        status="idle",
        setting_text="",
        bio_json=json.dumps(bio, ensure_ascii=False),
    )
    db_session.add(row)
    db_session.commit()
    return row


def _clear_bio_walk_flag():
    _ensure_app_migrations_table()
    with engine.connect() as conn:
        conn.execute(
            text("DELETE FROM app_migrations WHERE name = :name"),
            {"name": _BIO_WALK_FLAG},
        )
        conn.commit()


def _load_bio(db_session, char_id: str) -> dict:
    row = db_session.query(MaterialCharacter).filter_by(id=char_id).first()
    return json.loads(row.bio_json)


def _is_flag_applied() -> bool:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT 1 FROM app_migrations WHERE name = :name"),
            {"name": _BIO_WALK_FLAG},
        ).fetchone()
        return row is not None


@pytest.fixture(autouse=True)
def reset_bio_walk_flag():
    _clear_bio_walk_flag()
    yield
    _clear_bio_walk_flag()


def test_walk_adds_field_to_existing_entries(db_session):
    bio = {
        "official_seed_prompts": {
            "character_specific": [
                {"id": "1", "text": "a", "used": False},
                {"id": "2", "text": "b", "used": False},
                {"id": "3", "text": "c", "used": False},
            ],
            "general": [],
        }
    }
    char = _make_character(db_session, bio)
    migrate_bio_official_seed_prompts_add_direction_fk()

    updated_bio = _load_bio(db_session, char.id)
    cs = updated_bio["official_seed_prompts"]["character_specific"]
    assert all(entry.get("creative_direction_id") is None for entry in cs)
    assert _is_flag_applied()


def test_walk_skips_already_migrated(db_session):
    bio = {
        "official_seed_prompts": {
            "character_specific": [
                {"id": "1", "text": "a", "used": False, "creative_direction_id": "xxx"},
            ],
            "general": [],
        }
    }
    char = _make_character(db_session, bio)
    migrate_bio_official_seed_prompts_add_direction_fk()

    updated_bio = _load_bio(db_session, char.id)
    cs = updated_bio["official_seed_prompts"]["character_specific"]
    assert cs[0]["creative_direction_id"] == "xxx"


def test_walk_idempotent(db_session):
    bio = {
        "official_seed_prompts": {
            "character_specific": [{"id": "1", "text": "a", "used": False}],
            "general": [],
        }
    }
    _make_character(db_session, bio)
    migrate_bio_official_seed_prompts_add_direction_fk()
    migrate_bio_official_seed_prompts_add_direction_fk()
    assert _is_flag_applied()


def test_walk_skips_general(db_session):
    bio = {
        "official_seed_prompts": {
            "character_specific": [],
            "general": [{"id": "g1", "text": "legacy", "used": False}],
        }
    }
    char = _make_character(db_session, bio)
    migrate_bio_official_seed_prompts_add_direction_fk()

    updated_bio = _load_bio(db_session, char.id)
    general = updated_bio["official_seed_prompts"]["general"]
    assert "creative_direction_id" not in general[0]


def test_walk_handles_malformed_bio(db_session, caplog):
    char_id = f"mchar_{uuid.uuid4().hex[:10]}"
    row = MaterialCharacter(
        id=char_id,
        name="Bad",
        display_name="Bad",
        status="idle",
        setting_text="",
        bio_json="not json",
    )
    db_session.add(row)
    db_session.commit()

    migrate_bio_official_seed_prompts_add_direction_fk()
    assert _is_flag_applied()


def test_walk_marks_when_no_changes(db_session):
    char_id = f"mchar_{uuid.uuid4().hex[:10]}"
    row = MaterialCharacter(
        id=char_id,
        name="Empty",
        display_name="Empty",
        status="idle",
        setting_text="",
        bio_json="{}",
    )
    db_session.add(row)
    db_session.commit()

    migrate_bio_official_seed_prompts_add_direction_fk()
    assert _is_flag_applied()
