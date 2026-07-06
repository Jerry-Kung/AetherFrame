"""BeautifyService 单元测试。"""

import os
import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.models.creation import CreationQuickCreateTask  # noqa: F401
from app.models.material import MaterialCharacter  # noqa: F401
from app.repositories.beautify_repository import BeautifyRepository
from app.repositories.creation_repository import CreationQuickCreateRepository
from app.services.beautify_service import BeautifyService
from app.services.beautify_service.exceptions import BeautifyConflictError
from app.tools.beautify.enhancer import EnhanceResult


class MockStorage:
    def __init__(self):
        self.deletes: list[str] = []

    def upload_and_presign(self, local_path: str, object_key: str | None = None):
        key = object_key or f"tmp/test_{os.path.basename(local_path)}"
        return key, "https://example.com/signed"

    def delete(self, object_key: str) -> None:
        self.deletes.append(object_key)


class MockEnhancer:
    def submit(self, image_url: str) -> str:
        return "bigjpg-tid-1"

    def poll(self, external_task_id: str) -> EnhanceResult:
        return EnhanceResult(
            status="succeeded",
            result_url="https://cdn.example.com/result.png",
        )


@pytest.fixture
def quick_create_with_image(db_session, temp_data_dir):
    mrepo = __import__(
        "app.repositories.material_repository", fromlist=["MaterialCharacterRepository"]
    ).MaterialCharacterRepository(db_session)
    char_id = f"mchar_{uuid.uuid4().hex[:12]}"
    char = mrepo.create({"id": char_id, "name": "beautify-test-char"})
    qrepo = CreationQuickCreateRepository(db_session)
    task = qrepo.create(
        character_id=char.id,
        seed_prompt="seed",
        n=1,
        aspect_ratio="16:9",
        selected_prompts=[{"id": "p1", "fullPrompt": "prompt"}],
    )
    img_rel = "prompt_1_p1/out.png"
    img_dir = os.path.join(task.work_dir, "prompt_1_p1")
    os.makedirs(img_dir, exist_ok=True)
    img_abs = os.path.join(img_dir, "out.png")
    with open(img_abs, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
    return task.id, img_rel, img_abs


@patch("app.services.beautify_service.runner.resize_to_max_bytes")
@patch("app.services.beautify_service.runner.requests.get")
def test_start_returns_inflight_task(
    mock_get, mock_resize, db_session, quick_create_with_image
):
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.iter_content = lambda chunk_size=65536: [b"png"]
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_get.return_value = mock_resp
    qc_task_id, img_rel, _ = quick_create_with_image
    svc = BeautifyService(
        db_session,
        session_factory=lambda: db_session,
        storage=MockStorage(),
        enhancer=MockEnhancer(),
    )
    first = svc.start(
        source_kind="quick_create",
        source_task_id=qc_task_id,
        source_image_path=img_rel,
        background_tasks=None,
    )
    assert first["status"] == "completed"

    repo = BeautifyRepository(db_session)
    row = repo.get_by_source("quick_create", qc_task_id, img_rel)
    assert row is not None
    repo.update(row.id, {"status": "processing", "current_step": "polling"})

    second = svc.start(
        source_kind="quick_create",
        source_task_id=qc_task_id,
        source_image_path=img_rel,
        background_tasks=None,
    )
    assert second["task_id"] == row.id
    assert second["status"] == "processing"


@patch("app.services.beautify_service.runner.resize_to_max_bytes")
@patch("app.services.beautify_service.runner.requests.get")
def test_start_completed_raises_conflict(
    mock_get, mock_resize, db_session, quick_create_with_image
):
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.iter_content = lambda chunk_size=65536: [b"png"]
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_get.return_value = mock_resp
    qc_task_id, img_rel, _ = quick_create_with_image
    svc = BeautifyService(
        db_session,
        session_factory=lambda: db_session,
        storage=MockStorage(),
        enhancer=MockEnhancer(),
    )
    svc.start(
        source_kind="quick_create",
        source_task_id=qc_task_id,
        source_image_path=img_rel,
        background_tasks=None,
    )
    with pytest.raises(BeautifyConflictError):
        svc.start(
            source_kind="quick_create",
            source_task_id=qc_task_id,
            source_image_path=img_rel,
            background_tasks=None,
        )


@patch("app.services.beautify_service.runner.resize_to_max_bytes")
@patch("app.services.beautify_service.runner.requests.get")
def test_cleanup_for_quick_create(
    mock_get, mock_resize, db_session, quick_create_with_image
):
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.iter_content = lambda chunk_size=65536: [b"png"]
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_get.return_value = mock_resp
    qc_task_id, img_rel, _ = quick_create_with_image
    storage = MockStorage()
    svc = BeautifyService(
        db_session,
        session_factory=lambda: db_session,
        storage=storage,
        enhancer=MockEnhancer(),
    )
    svc.start(
        source_kind="quick_create",
        source_task_id=qc_task_id,
        source_image_path=img_rel,
        background_tasks=None,
    )
    count = svc.cleanup_for_quick_create_task(qc_task_id)
    assert count == 1
    assert BeautifyRepository(db_session).get_by_source("quick_create", qc_task_id, img_rel) is None
