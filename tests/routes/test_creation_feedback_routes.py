"""feedback 保存 / 导出 / hydrated 回显路由测试"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.repositories.creation_repository import CreationQuickCreateRepository
from app.repositories.material_repository import MaterialCharacterRepository


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


QC_RESULTS = [
    {
        "prompt_id": "p1",
        "full_prompt": "最终 Prompt 甲",
        "generated_images": [{"filename": "a0.png", "path": "images/a0.png"}],
    }
]


def _make_qc_task(db_session):
    char = MaterialCharacterRepository(db_session).create(
        {"id": f"mchar_{uuid.uuid4().hex[:12]}", "name": "fb-route-char"}
    )
    repo = CreationQuickCreateRepository(db_session)
    task = repo.create(
        character_id=char.id, seed_prompt="种子", n=1, aspect_ratio="1:1",
        selected_prompts=[], status="completed",
    )
    return repo.update(task.id, {"result_json": QC_RESULTS})


def _fb_url(task_id, prompt_id="p1", index=0):
    return f"/api/creation/quick-create/tasks/{task_id}/feedback/{prompt_id}/{index}"


def test_save_and_clear_feedback(api_client, db_session):
    task = _make_qc_task(db_session)
    r = api_client.put(_fb_url(task.id), json={"feedback_text": "脚部简陋", "leg_foot_bad": True})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["data"] == {
        "prompt_id": "p1", "image_index": 0,
        "leg_foot_bad": True, "feedback_text": "脚部简陋",
        "selected_tags": [],
    }
    # 清空即删
    r2 = api_client.put(_fb_url(task.id), json={"feedback_text": "", "leg_foot_bad": False})
    assert r2.status_code == 200
    assert r2.json()["data"] is None


def test_save_missing_task_404(api_client):
    r = api_client.put(_fb_url("qcreate_missing0000"), json={"feedback_text": "x", "leg_foot_bad": False})
    assert r.status_code == 404


def test_save_negative_index_422(api_client, db_session):
    task = _make_qc_task(db_session)
    r = api_client.put(_fb_url(task.id, index=-1), json={"feedback_text": "x", "leg_foot_bad": False})
    assert r.status_code == 422


def test_export_endpoint(api_client, db_session):
    task = _make_qc_task(db_session)
    api_client.put(_fb_url(task.id), json={"feedback_text": "备注", "leg_foot_bad": True})
    r = api_client.get("/api/creation/feedback/export")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["schema"] == "aetherframe_feedback_v2"
    assert "tag_config" in data
    assert len(data["records"]) == 1
    assert data["records"][0]["quick_create_task_id"] == task.id


def test_hydrated_items_include_feedbacks(api_client, db_session):
    from app.repositories.creation_batch_repository import CreationBatchRepository

    task = _make_qc_task(db_session)
    repo = CreationBatchRepository(db_session)
    run = repo.create_run(iterations_total=1, config_json="{}", status="completed")
    item = repo.create_item(
        run_id=run.id, step_index=0, character_id=task.character_id,
        seed_prompt_id="s1", seed_section="general", seed_prompt_text="seed",
        status="completed",
    )
    repo.update_item(item.id, {"quick_create_task_id": task.id})
    api_client.put(_fb_url(task.id), json={"feedback_text": "回显", "leg_foot_bad": False})

    r = api_client.get("/api/creation/batch-automation/items-hydrated")
    assert r.status_code == 200
    items = r.json()["data"]["items"]
    row = next(x for x in items if x["id"] == item.id)
    assert row["feedbacks"] == [
        {"prompt_id": "p1", "image_index": 0,
         "leg_foot_bad": False, "feedback_text": "回显", "selected_tags": []}
    ]


def test_feedback_tags_api(api_client):
    r = api_client.get("/api/creation/feedback/tags")
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    data = body["data"]
    assert data["version"] >= 1
    by_key = {t["key"]: t for t in data["tags"]}
    assert by_key["sock_wrinkle_heavy"] == {
        "key": "sock_wrinkle_heavy", "label": "袜子皱褶过于夸张",
        "polarity": "negative", "leg_foot_bad": True, "group": "袜子",
    }
    assert by_key["neutral_normal"]["polarity"] == "neutral"
    # taxonomy 不下发
    assert all("taxonomy" not in t for t in data["tags"])


def test_feedback_tags_api_degrades_when_config_missing(api_client, monkeypatch):
    from app.services.creation_service import feedback_tags

    monkeypatch.setattr(
        feedback_tags, "get_tag_config", lambda: {"version": 0, "tags": []}
    )
    r = api_client.get("/api/creation/feedback/tags")
    assert r.status_code == 200
    assert r.json()["data"] == {"version": 0, "tags": []}


def test_save_with_selected_tags_roundtrip(api_client, db_session):
    task = _make_qc_task(db_session)
    r = api_client.put(_fb_url(task.id), json={
        "feedback_text": "",
        "leg_foot_bad": False,
        "selected_tags": [
            {"key": "sock_toe_separation", "severity": "minor"},
            {"key": "pos_sock_style"},
        ],
    })
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["selected_tags"] == [
        {"key": "sock_toe_separation", "severity": "minor"},
        {"key": "pos_sock_style"},
    ]
    assert data["leg_foot_bad"] is True  # sock_toe_separation 计 bad

    # 回显同样带标签
    from app.repositories.creation_batch_repository import CreationBatchRepository
    repo = CreationBatchRepository(db_session)
    run = repo.create_run(iterations_total=1, config_json="{}", status="completed")
    item = repo.create_item(
        run_id=run.id, step_index=0, character_id=task.character_id,
        seed_prompt_id="s1", seed_section="general", seed_prompt_text="seed",
        status="completed",
    )
    repo.update_item(item.id, {"quick_create_task_id": task.id})
    r2 = api_client.get("/api/creation/batch-automation/items-hydrated")
    row = next(x for x in r2.json()["data"]["items"] if x["id"] == item.id)
    assert row["feedbacks"][0]["selected_tags"] == [
        {"key": "sock_toe_separation", "severity": "minor"},
        {"key": "pos_sock_style"},
    ]


def test_save_body_without_selected_tags_still_works(api_client, db_session):
    # 向后兼容：旧 body 不带 selected_tags
    task = _make_qc_task(db_session)
    r = api_client.put(_fb_url(task.id), json={"feedback_text": "老格式", "leg_foot_bad": False})
    assert r.status_code == 200
    assert r.json()["data"]["selected_tags"] == []
