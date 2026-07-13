"""批量删除产线记录路由：请求校验与结果分类"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.repositories.creation_batch_repository import CreationBatchRepository
from app.repositories.material_repository import MaterialCharacterRepository

URL = "/api/creation/batch-automation/items/batch-delete"


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


def _make_item(db_session, status="completed"):
    char = MaterialCharacterRepository(db_session).create(
        {"id": f"mchar_{uuid.uuid4().hex[:12]}", "name": "route-bulk-char"}
    )
    batch_repo = CreationBatchRepository(db_session)
    run = batch_repo.create_run(iterations_total=1, config_json="{}", status="completed")
    return batch_repo.create_item(
        run_id=run.id,
        step_index=0,
        character_id=char.id,
        seed_prompt_id="s1",
        seed_section="general",
        seed_prompt_text="seed",
        status=status,
    )


def test_batch_delete_dedups_and_classifies(api_client, db_session):
    """去重去空白；completed 删除、running 跳过、不存在归 not_found；恒 200。"""
    done = _make_item(db_session)
    running = _make_item(db_session, status="running")

    r = api_client.post(
        URL,
        json={"item_ids": [done.id, f"  {done.id}  ", "", running.id, "bb_item_gone0000"]},
    )

    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    data = body["data"]
    assert data["deleted"] == [done.id]
    assert data["skipped_running"] == [running.id]
    assert data["not_found"] == ["bb_item_gone0000"]
    assert data["failed"] == []


def test_batch_delete_empty_after_clean_returns_400(api_client):
    r = api_client.post(URL, json={"item_ids": ["   ", ""]})
    assert r.status_code == 400


def test_batch_delete_empty_list_returns_422(api_client):
    r = api_client.post(URL, json={"item_ids": []})
    assert r.status_code == 422


def test_batch_delete_over_200_returns_422(api_client):
    r = api_client.post(URL, json={"item_ids": [f"id_{i}" for i in range(201)]})
    assert r.status_code == 422
