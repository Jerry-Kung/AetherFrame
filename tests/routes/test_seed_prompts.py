import json
import os
import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.config import (
    MATERIAL_SEED_PROMPT_PER_CHARACTER_LIMIT,
    MATERIAL_SEED_PROMPT_PER_DIRECTION_LIMIT,
)
from app.models.material import (
    MaterialCharacter,
    MaterialCreativeDirection,
    MaterialCreativeDirectionTask,
    MaterialSeedPromptTask,
)
from app.schemas.material import MaterialErrorCode


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
            name="Route",
            display_name="Route",
            status="idle",
            setting_text="",
        )
    )
    db_session.commit()
    return char_id


@patch("app.services.material_service.material_service.run_seed_prompt_task")
def test_start_returns_task_row(mock_run, api_client, db_session):
    char_id = _create_character(db_session)
    r = api_client.post(
        f"/api/material/characters/{char_id}/seed-prompts/start",
        json={"creative_direction_id": None},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["data"]["status"] == "pending"
    task_id = body["data"]["task_id"]
    task = db_session.query(MaterialSeedPromptTask).filter_by(id=task_id).first()
    assert task is not None
    mock_run.assert_called_once()


def test_status_after_mock_completion(api_client, db_session):
    char_id = _create_character(db_session)
    task_id = str(uuid.uuid4())
    db_session.add(
        MaterialSeedPromptTask(
            id=task_id,
            character_id=char_id,
            status="completed",
        )
    )
    db_session.commit()

    draft_payload = {"character_specific": ["draft1"]}

    with patch(
        "app.services.material_service.material_service.read_seed_draft_file",
        return_value=draft_payload,
    ):
        r = api_client.get(f"/api/material/characters/{char_id}/seed-prompts/tasks/{task_id}")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["seed_draft"]["character_specific"] == ["draft1"]


def test_start_409_per_direction(api_client, db_session):
    char_id = _create_character(db_session)
    direction_id = str(uuid.uuid4())
    db_session.add(
        MaterialCreativeDirection(
            id=direction_id,
            character_id=char_id,
            title="T",
            description="D",
            divergence="low",
        )
    )
    cs = [
        {
            "id": str(i),
            "text": f"s{i}",
            "used": False,
            "creative_direction_id": direction_id,
        }
        for i in range(MATERIAL_SEED_PROMPT_PER_DIRECTION_LIMIT)
    ]
    db_session.query(MaterialCharacter).filter_by(id=char_id).update(
        {
            "bio_json": json.dumps(
                {"official_seed_prompts": {"character_specific": cs, "general": []}},
                ensure_ascii=False,
            )
        }
    )
    db_session.commit()

    r = api_client.post(
        f"/api/material/characters/{char_id}/seed-prompts/start",
        json={"creative_direction_id": direction_id},
    )
    assert r.status_code == 409
    assert r.json()["code"] == MaterialErrorCode.SEED_PER_DIRECTION_EXCEEDED.value


def test_start_409_total(api_client, db_session):
    char_id = _create_character(db_session)
    cs = [
        {"id": str(i), "text": f"s{i}", "used": False, "creative_direction_id": None}
        for i in range(MATERIAL_SEED_PROMPT_PER_CHARACTER_LIMIT)
    ]
    db_session.query(MaterialCharacter).filter_by(id=char_id).update(
        {
            "bio_json": json.dumps(
                {"official_seed_prompts": {"character_specific": cs, "general": []}},
                ensure_ascii=False,
            )
        }
    )
    db_session.commit()

    r = api_client.post(
        f"/api/material/characters/{char_id}/seed-prompts/start",
        json={"creative_direction_id": None},
    )
    assert r.status_code == 409
    assert r.json()["code"] == MaterialErrorCode.SEED_TOTAL_EXCEEDED.value


@patch("app.services.material_service.material_service.run_seed_prompt_task")
def test_start_409_concurrency_combined(mock_run, api_client, db_session):
    char_id = _create_character(db_session)
    db_session.add_all(
        [
            MaterialCreativeDirectionTask(
                id=str(uuid.uuid4()),
                character_id=char_id,
                status="pending",
                divergence="low",
            ),
            MaterialSeedPromptTask(
                id=str(uuid.uuid4()),
                character_id=char_id,
                status="processing",
            ),
        ]
    )
    db_session.commit()

    r = api_client.post(
        f"/api/material/characters/{char_id}/seed-prompts/start",
        json={"creative_direction_id": None},
    )
    assert r.status_code == 409
    assert r.json()["code"] == MaterialErrorCode.TASK_CONCURRENCY_EXCEEDED.value
    mock_run.assert_not_called()


def test_start_with_invalid_direction_returns_404(api_client, db_session):
    char_id = _create_character(db_session)
    other_id = _create_character(db_session)
    direction_id = str(uuid.uuid4())
    db_session.add(
        MaterialCreativeDirection(
            id=direction_id,
            character_id=other_id,
            title="T",
            description="D",
            divergence="low",
        )
    )
    db_session.commit()

    r = api_client.post(
        f"/api/material/characters/{char_id}/seed-prompts/start",
        json={"creative_direction_id": direction_id},
    )
    assert r.status_code == 404


@patch("app.services.material_service.material_service.run_seed_prompt_task")
def test_start_with_null_direction_ok(mock_run, api_client, db_session):
    char_id = _create_character(db_session)
    r = api_client.post(
        f"/api/material/characters/{char_id}/seed-prompts/start",
        json={"creative_direction_id": None},
    )
    assert r.status_code == 200
    mock_run.assert_called_once()


def test_status_cross_character_returns_404(api_client, db_session):
    char_a = _create_character(db_session)
    char_b = _create_character(db_session)
    task_id = str(uuid.uuid4())
    db_session.add(
        MaterialSeedPromptTask(
            id=task_id,
            character_id=char_a,
            status="completed",
        )
    )
    db_session.commit()

    r = api_client.get(f"/api/material/characters/{char_b}/seed-prompts/tasks/{task_id}")
    assert r.status_code == 404
