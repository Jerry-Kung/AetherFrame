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


def _create_character(db_session) -> str:
    char_id = f"mchar_{uuid.uuid4().hex[:10]}"
    db_session.add(
        MaterialCharacter(
            id=char_id,
            name="Bio",
            display_name="Bio",
            status="idle",
            setting_text="",
        )
    )
    db_session.commit()
    return char_id


def test_patch_bio_rejects_creative_advice(api_client, db_session):
    char_id = _create_character(db_session)
    r = api_client.patch(
        f"/api/material/characters/{char_id}/bio",
        json={"creative_advice": "legacy text"},
    )
    assert r.status_code == 400
    assert "creative_advice" in r.json()["detail"]


def test_patch_bio_accepts_creative_direction_id_on_cs(api_client, db_session):
    char_id = _create_character(db_session)
    direction_id = str(uuid.uuid4())
    db_session.add(
        MaterialCreativeDirection(
            id=direction_id,
            character_id=char_id,
            title="Dir",
            description="Desc",
            divergence="low",
        )
    )
    db_session.commit()

    payload = {
        "official_seed_prompts": {
            "character_specific": [
                {
                    "id": "s1",
                    "text": "seed text",
                    "used": False,
                    "creative_direction_id": direction_id,
                }
            ],
            "general": [],
        }
    }
    r = api_client.patch(f"/api/material/characters/{char_id}/bio", json=payload)
    assert r.status_code == 200
    bio = json.loads(
        db_session.query(MaterialCharacter).filter_by(id=char_id).first().bio_json
    )
    cs = bio["official_seed_prompts"]["character_specific"]
    assert cs[0]["creative_direction_id"] == direction_id


def test_patch_bio_coerces_other_owner_direction_id_to_null(api_client, db_session):
    char_id = _create_character(db_session)
    other_id = _create_character(db_session)
    direction_id = str(uuid.uuid4())
    db_session.add(
        MaterialCreativeDirection(
            id=direction_id,
            character_id=other_id,
            title="Other",
            description="D",
            divergence="low",
        )
    )
    db_session.commit()

    r = api_client.patch(
        f"/api/material/characters/{char_id}/bio",
        json={
            "official_seed_prompts": {
                "character_specific": [
                    {
                        "id": "s1",
                        "text": "x",
                        "used": False,
                        "creative_direction_id": direction_id,
                    }
                ],
                "general": [],
            }
        },
    )
    assert r.status_code == 200
    bio = json.loads(
        db_session.query(MaterialCharacter).filter_by(id=char_id).first().bio_json
    )
    cs = bio["official_seed_prompts"]["character_specific"]
    assert cs[0]["creative_direction_id"] is None


def test_patch_bio_coerces_nonexistent_direction_id_on_cs_to_null(api_client, db_session):
    char_id = _create_character(db_session)
    r = api_client.patch(
        f"/api/material/characters/{char_id}/bio",
        json={
            "official_seed_prompts": {
                "character_specific": [
                    {
                        "id": "s1",
                        "text": "x",
                        "used": False,
                        "creative_direction_id": "nonexistent-dir",
                    }
                ],
                "general": [],
            }
        },
    )
    assert r.status_code == 200
    bio = json.loads(
        db_session.query(MaterialCharacter).filter_by(id=char_id).first().bio_json
    )
    cs = bio["official_seed_prompts"]["character_specific"]
    assert cs[0]["creative_direction_id"] is None


def test_patch_bio_strips_direction_id_from_general(api_client, db_session, caplog):
    char_id = _create_character(db_session)
    r = api_client.patch(
        f"/api/material/characters/{char_id}/bio",
        json={
            "official_seed_prompts": {
                "character_specific": [],
                "general": [
                    {
                        "id": "g1",
                        "text": "legacy",
                        "used": False,
                        "creative_direction_id": "should-strip",
                    }
                ],
            }
        },
    )
    assert r.status_code == 200
    bio = json.loads(
        db_session.query(MaterialCharacter).filter_by(id=char_id).first().bio_json
    )
    assert "creative_direction_id" not in bio["official_seed_prompts"]["general"][0]


def test_patch_bio_null_direction_id_on_cs_ok(api_client, db_session):
    char_id = _create_character(db_session)
    r = api_client.patch(
        f"/api/material/characters/{char_id}/bio",
        json={
            "official_seed_prompts": {
                "character_specific": [
                    {"id": "s1", "text": "x", "used": False, "creative_direction_id": None}
                ],
                "general": [],
            }
        },
    )
    assert r.status_code == 200


def test_delete_creative_direction_detaches_seeds_in_bio(api_client, db_session):
    char_id = _create_character(db_session)
    direction_id = str(uuid.uuid4())
    db_session.add(
        MaterialCreativeDirection(
            id=direction_id,
            character_id=char_id,
            title="Dir",
            description="Desc",
            divergence="low",
        )
    )
    db_session.commit()

    api_client.patch(
        f"/api/material/characters/{char_id}/bio",
        json={
            "official_seed_prompts": {
                "character_specific": [
                    {
                        "id": "s_bound",
                        "text": "bound",
                        "used": False,
                        "creative_direction_id": direction_id,
                    },
                    {
                        "id": "s_free",
                        "text": "free",
                        "used": False,
                        "creative_direction_id": None,
                    },
                ],
                "general": [],
            }
        },
    )

    r = api_client.delete(
        f"/api/material/characters/{char_id}/creative-directions/{direction_id}"
    )
    assert r.status_code == 200

    db_session.expire_all()
    bio = json.loads(
        db_session.query(MaterialCharacter).filter_by(id=char_id).first().bio_json
    )
    cs = {s["id"]: s for s in bio["official_seed_prompts"]["character_specific"]}
    assert cs["s_bound"]["creative_direction_id"] is None
    assert cs["s_free"]["creative_direction_id"] is None
