import os
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.config import MATERIAL_CREATIVE_DIRECTION_PER_CHARACTER_LIMIT
from app.models.material import (
    MaterialCharacter,
    MaterialCreativeDirection,
    MaterialCreativeDirectionTask,
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


@patch("app.services.material_service.material_service.run_creative_direction_task")
def test_start_returns_task_row(mock_run, api_client, db_session):
    char_id = _create_character(db_session)
    r = api_client.post(
        f"/api/material/characters/{char_id}/creative-directions/start",
        json={"divergence": "low", "initial_input": "治愈"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["data"]["status"] == "pending"
    task_id = body["data"]["task_id"]
    task = db_session.query(MaterialCreativeDirectionTask).filter_by(id=task_id).first()
    assert task is not None
    assert task.status == "pending"
    mock_run.assert_called_once()


def test_status_after_mock_completion(api_client, db_session):
    char_id = _create_character(db_session)
    task_id = str(uuid.uuid4())
    direction_id = str(uuid.uuid4())
    db_session.add_all(
        [
            MaterialCreativeDirectionTask(
                id=task_id,
                character_id=char_id,
                status="completed",
                divergence="mid",
                result_direction_id=direction_id,
            ),
            MaterialCreativeDirection(
                id=direction_id,
                character_id=char_id,
                title="T",
                description="D",
                divergence="mid",
            ),
        ]
    )
    db_session.commit()
    r = api_client.get(
        f"/api/material/characters/{char_id}/creative-directions/tasks/{task_id}"
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["result_direction"] is not None
    assert data["result_direction"]["title"] == "T"


def test_start_409_at_limit(api_client, db_session):
    char_id = _create_character(db_session)
    for i in range(MATERIAL_CREATIVE_DIRECTION_PER_CHARACTER_LIMIT):
        db_session.add(
            MaterialCreativeDirection(
                id=str(uuid.uuid4()),
                character_id=char_id,
                title=f"T{i}",
                description="D",
                divergence="low",
            )
        )
    db_session.commit()
    r = api_client.post(
        f"/api/material/characters/{char_id}/creative-directions/start",
        json={"divergence": "low"},
    )
    assert r.status_code == 409
    assert r.json()["code"] == MaterialErrorCode.DIRECTION_LIMIT_EXCEEDED.value


def test_start_409_concurrent(api_client, db_session):
    char_id = _create_character(db_session)
    for _ in range(2):
        db_session.add(
            MaterialCreativeDirectionTask(
                id=str(uuid.uuid4()),
                character_id=char_id,
                status="pending",
                divergence="low",
            )
        )
    db_session.commit()
    r = api_client.post(
        f"/api/material/characters/{char_id}/creative-directions/start",
        json={"divergence": "high"},
    )
    assert r.status_code == 409
    assert r.json()["code"] == MaterialErrorCode.TASK_CONCURRENCY_EXCEEDED.value


def test_list_orders_desc(api_client, db_session):
    char_id = _create_character(db_session)
    now = datetime.now(timezone.utc)
    ids = []
    for i, days in enumerate([2, 1, 0]):
        did = str(uuid.uuid4())
        ids.append(did)
        db_session.add(
            MaterialCreativeDirection(
                id=did,
                character_id=char_id,
                title=f"T{i}",
                description="D",
                divergence="low",
                created_at=now - timedelta(days=days),
            )
        )
    db_session.commit()
    r = api_client.get(f"/api/material/characters/{char_id}/creative-directions")
    titles = [x["title"] for x in r.json()["data"]]
    assert titles == ["T2", "T1", "T0"]


def test_list_empty(api_client, db_session):
    char_id = _create_character(db_session)
    r = api_client.get(f"/api/material/characters/{char_id}/creative-directions")
    assert r.json()["data"] == []


def test_patch_title_only(api_client, db_session):
    char_id = _create_character(db_session)
    did = str(uuid.uuid4())
    db_session.add(
        MaterialCreativeDirection(
            id=did,
            character_id=char_id,
            title="Old",
            description="Desc",
            divergence="low",
        )
    )
    db_session.commit()
    r = api_client.patch(
        f"/api/material/characters/{char_id}/creative-directions/{did}",
        json={"title": "新"},
    )
    assert r.status_code == 200
    assert r.json()["data"]["title"] == "新"
    assert r.json()["data"]["description"] == "Desc"


def test_patch_both(api_client, db_session):
    char_id = _create_character(db_session)
    did = str(uuid.uuid4())
    db_session.add(
        MaterialCreativeDirection(
            id=did,
            character_id=char_id,
            title="Old",
            description="OldD",
            divergence="low",
        )
    )
    db_session.commit()
    r = api_client.patch(
        f"/api/material/characters/{char_id}/creative-directions/{did}",
        json={"title": "新", "description": "新D"},
    )
    assert r.json()["data"]["title"] == "新"
    assert r.json()["data"]["description"] == "新D"


def test_patch_neither_returns_400(api_client, db_session):
    char_id = _create_character(db_session)
    did = str(uuid.uuid4())
    db_session.add(
        MaterialCreativeDirection(
            id=did,
            character_id=char_id,
            title="T",
            description="D",
            divergence="low",
        )
    )
    db_session.commit()
    r = api_client.patch(
        f"/api/material/characters/{char_id}/creative-directions/{did}",
        json={},
    )
    assert r.status_code == 400


def test_patch_cross_character_returns_404(api_client, db_session):
    char_a = _create_character(db_session)
    char_b = _create_character(db_session)
    did = str(uuid.uuid4())
    db_session.add(
        MaterialCreativeDirection(
            id=did,
            character_id=char_a,
            title="T",
            description="D",
            divergence="low",
        )
    )
    db_session.commit()
    r = api_client.patch(
        f"/api/material/characters/{char_b}/creative-directions/{did}",
        json={"title": "x"},
    )
    assert r.status_code == 404


def test_delete_removes_row_and_file(api_client, db_session, temp_data_dir):
    char_id = _create_character(db_session)
    did = str(uuid.uuid4())
    db_session.add(
        MaterialCreativeDirection(
            id=did,
            character_id=char_id,
            title="T",
            description="D",
            divergence="low",
        )
    )
    db_session.commit()
    from app.services.material_service import material_file_service

    dir_path = os.path.join(
        material_file_service.get_character_dir(char_id), "creative_directions"
    )
    os.makedirs(dir_path, exist_ok=True)
    file_path = os.path.join(dir_path, f"{did}.json")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("{}")
    r = api_client.delete(
        f"/api/material/characters/{char_id}/creative-directions/{did}"
    )
    assert r.status_code == 200
    assert db_session.query(MaterialCreativeDirection).filter_by(id=did).count() == 0
    assert not os.path.isfile(file_path)


def test_delete_cross_character_returns_404(api_client, db_session):
    char_a = _create_character(db_session)
    char_b = _create_character(db_session)
    did = str(uuid.uuid4())
    db_session.add(
        MaterialCreativeDirection(
            id=did,
            character_id=char_a,
            title="T",
            description="D",
            divergence="low",
        )
    )
    db_session.commit()
    r = api_client.delete(
        f"/api/material/characters/{char_b}/creative-directions/{did}"
    )
    assert r.status_code == 404


def test_status_cross_character_returns_404(api_client, db_session):
    char_a = _create_character(db_session)
    char_b = _create_character(db_session)
    task_id = str(uuid.uuid4())
    db_session.add(
        MaterialCreativeDirectionTask(
            id=task_id,
            character_id=char_a,
            status="pending",
            divergence="low",
        )
    )
    db_session.commit()
    r = api_client.get(
        f"/api/material/characters/{char_b}/creative-directions/tasks/{task_id}"
    )
    assert r.status_code == 404
