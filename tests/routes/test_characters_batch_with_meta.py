import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app.models.material import MaterialCharacter, MaterialCreativeDirection


@pytest.fixture
def api_client(db_session):
    from app.main import app
    from app.models.database import get_db

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _create_character_with_bio(db_session, bio: dict) -> str:
    char_id = f"mchar_{uuid.uuid4().hex[:10]}"
    db_session.add(
        MaterialCharacter(
            id=char_id,
            name="Meta",
            display_name="Meta",
            status="done",
            setting_text="",
            bio_json=json.dumps(bio, ensure_ascii=False),
        )
    )
    db_session.commit()
    return char_id


def test_batch_returns_seeds_with_meta(api_client, db_session):
    char_id = _create_character_with_bio(
        db_session,
        {
            "official_seed_prompts": {
                "character_specific": [{"id": "s1", "text": "t", "used": False}],
                "general": [],
            }
        },
    )
    dir_id = str(uuid.uuid4())
    db_session.add(
        MaterialCreativeDirection(
            id=dir_id,
            character_id=char_id,
            title="批方向",
            description="d",
            divergence="low",
        )
    )
    db_session.commit()
    bio = json.loads(db_session.query(MaterialCharacter).filter_by(id=char_id).first().bio_json)
    bio["official_seed_prompts"]["character_specific"][0]["creative_direction_id"] = dir_id
    db_session.query(MaterialCharacter).filter_by(id=char_id).update(
        {"bio_json": json.dumps(bio, ensure_ascii=False)}
    )
    db_session.commit()

    r = api_client.get(f"/api/material/characters/batch?ids={char_id}")
    assert r.status_code == 200
    data = r.json()["data"]
    cs = data[0]["bio"]["official_seed_prompts"]["character_specific"]
    assert "creative_direction_meta" in cs[0]
    assert cs[0]["creative_direction_meta"]["title"] == "批方向"


def test_batch_meta_null_when_no_direction(api_client, db_session):
    char_id = _create_character_with_bio(
        db_session,
        {
            "official_seed_prompts": {
                "character_specific": [
                    {"id": "s1", "text": "t", "used": False, "creative_direction_id": None}
                ],
                "general": [],
            }
        },
    )
    r = api_client.get(f"/api/material/characters/batch?ids={char_id}")
    cs = r.json()["data"][0]["bio"]["official_seed_prompts"]["character_specific"]
    assert cs[0]["creative_direction_meta"] is None


def test_batch_general_no_meta(api_client, db_session):
    char_id = _create_character_with_bio(
        db_session,
        {
            "official_seed_prompts": {
                "character_specific": [],
                "general": [{"id": "g1", "text": "legacy", "used": False}],
            }
        },
    )
    r = api_client.get(f"/api/material/characters/batch?ids={char_id}")
    general = r.json()["data"][0]["bio"]["official_seed_prompts"]["general"]
    assert "creative_direction_meta" not in general[0]


def test_single_get_returns_seeds_with_meta(api_client, db_session):
    char_id = _create_character_with_bio(
        db_session,
        {
            "official_seed_prompts": {
                "character_specific": [
                    {"id": "s1", "text": "t", "used": False, "creative_direction_id": None}
                ],
                "general": [],
            }
        },
    )
    dir_id = str(uuid.uuid4())
    db_session.add(
        MaterialCreativeDirection(
            id=dir_id,
            character_id=char_id,
            title="单角色",
            description="d",
            divergence="mid",
        )
    )
    db_session.commit()
    bio = json.loads(db_session.query(MaterialCharacter).filter_by(id=char_id).first().bio_json)
    bio["official_seed_prompts"]["character_specific"][0]["creative_direction_id"] = dir_id
    db_session.query(MaterialCharacter).filter_by(id=char_id).update(
        {"bio_json": json.dumps(bio, ensure_ascii=False)}
    )
    db_session.commit()

    r = api_client.get(f"/api/material/characters/{char_id}")
    cs = r.json()["data"]["bio"]["official_seed_prompts"]["character_specific"]
    assert cs[0]["creative_direction_meta"]["title"] == "单角色"
