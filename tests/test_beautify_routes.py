"""Beautify API 路由测试。"""

import os
import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.models.creation import CreationQuickCreateTask  # noqa: F401
from app.models.material import MaterialCharacter  # noqa: F401
from app.services.beautify_service import BeautifyService


@pytest.fixture
def api_client(db_session):
    from app.main import app
    from app.models.database import get_db

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def quick_create_image(db_session):
    from app.repositories.creation_repository import CreationQuickCreateRepository
    from app.repositories.material_repository import MaterialCharacterRepository

    mrepo = MaterialCharacterRepository(db_session)
    char_id = f"mchar_{uuid.uuid4().hex[:12]}"
    mrepo.create({"id": char_id, "name": "route-test"})
    qrepo = CreationQuickCreateRepository(db_session)
    task = qrepo.create(
        character_id=char_id,
        seed_prompt="seed",
        n=1,
        aspect_ratio="16:9",
        selected_prompts=[{"id": "p1", "fullPrompt": "prompt"}],
    )
    img_rel = "prompt_1_p1/out.png"
    os.makedirs(os.path.join(task.work_dir, "prompt_1_p1"), exist_ok=True)
    with open(os.path.join(task.work_dir, img_rel), "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
    return task.id, img_rel


@patch("app.services.beautify_service.runner.get_default_enhancer")
@patch("app.services.beautify_service.runner.get_default_client")
@patch("app.services.beautify_service.runner.resize_to_max_bytes")
@patch("app.services.beautify_service.runner.requests.get")
def test_beautify_routes_flow(
    mock_get,
    mock_resize,
    mock_get_storage,
    mock_get_enhancer,
    api_client,
    db_session,
    quick_create_image,
):
    from tests.test_beautify_service import MockEnhancer, MockStorage

    storage = MockStorage()
    enhancer = MockEnhancer()
    mock_get_storage.return_value = storage
    mock_get_enhancer.return_value = enhancer
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.iter_content = lambda chunk_size=65536: [b"png"]
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_get.return_value = mock_resp

    qc_id, img_rel = quick_create_image
    svc = BeautifyService(
        db_session,
        session_factory=lambda: db_session,
        storage=storage,
        enhancer=enhancer,
    )
    started = svc.start(
        source_kind="quick_create",
        source_task_id=qc_id,
        source_image_path=img_rel,
        background_tasks=None,
    )
    task_id = started["task_id"]

    status = api_client.get(f"/api/beautify/tasks/{task_id}/status")
    assert status.status_code == 200
    assert status.json()["data"]["status"] == "completed"

    with patch("app.tools.beautify.storage.get_default_client", return_value=storage):
        deleted = api_client.delete(f"/api/beautify/tasks/{task_id}")
    assert deleted.status_code == 200
    assert deleted.json()["data"]["deleted_id"] == task_id
