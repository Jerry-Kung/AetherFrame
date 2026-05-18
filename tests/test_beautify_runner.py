"""run_beautify_task_sync 集成测试（mock 外部 client）。"""

import os
import uuid
from unittest.mock import patch

import pytest

from app.models.creation import CreationQuickCreateTask  # noqa: F401
from app.models.material import MaterialCharacter  # noqa: F401
from app.repositories.beautify_repository import BeautifyRepository
from app.repositories.creation_repository import CreationQuickCreateRepository
from app.services.beautify_service.runner import run_beautify_task_sync
from app.tools.beautify.enhancer import EnhanceResult
from tests.test_beautify_service import MockEnhancer, MockStorage


@pytest.fixture
def beautify_task_row(db_session, temp_data_dir):
    mrepo = __import__(
        "app.repositories.material_repository", fromlist=["MaterialCharacterRepository"]
    ).MaterialCharacterRepository(db_session)
    char_id = f"mchar_{uuid.uuid4().hex[:12]}"
    char = mrepo.create({"id": char_id, "name": "runner-char"})
    qrepo = CreationQuickCreateRepository(db_session)
    task = qrepo.create(
        character_id=char.id,
        seed_prompt="seed",
        n=1,
        aspect_ratio="16:9",
        selected_prompts=[{"id": "p1", "fullPrompt": "prompt"}],
    )
    img_rel = "prompt_1_p1/out.png"
    os.makedirs(os.path.join(task.work_dir, "prompt_1_p1"), exist_ok=True)
    with open(os.path.join(task.work_dir, img_rel), "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")

    brepo = BeautifyRepository(db_session)
    bty = brepo.create(
        {
            "id": f"bty_{__import__('uuid').uuid4().hex[:12]}",
            "source_kind": "quick_create",
            "source_task_id": task.id,
            "source_image_path": img_rel,
            "status": "pending",
        }
    )
    return bty, task, img_rel


class TestBeautifyRunner:
    @patch("app.services.beautify_service.runner.requests.get")
    @patch("app.services.beautify_service.runner.resize_to_max_bytes")
    def test_runner_completes_and_deletes_cloud(
        self, mock_resize, mock_get, db_session, beautify_task_row
    ):
        bty, qc_task, img_rel = beautify_task_row
        work_dir = qc_task.work_dir
        storage = MockStorage()
        enhancer = MockEnhancer()

        from unittest.mock import MagicMock

        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.iter_content = lambda chunk_size=65536: [b"png-bytes"]
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_get.return_value = mock_resp

        def _session_factory():
            return db_session

        run_beautify_task_sync(
            bty.id,
            _session_factory,
            storage=storage,
            enhancer=enhancer,
        )

        brepo = BeautifyRepository(db_session)
        row = brepo.get_by_id(bty.id)
        assert row.status == "completed"
        assert row.beautified_filename == "out_beautified.png"
        assert row.cloud_object_key in storage.deletes

        beautified = os.path.join(work_dir, "prompt_1_p1", "out_beautified.png")
        assert os.path.isfile(beautified)
        mock_resize.assert_called_once()

    @patch("app.services.beautify_service.runner.requests.get")
    def test_runner_failed_still_deletes_cloud(
        self, mock_get, db_session, beautify_task_row
    ):
        bty, _, _ = beautify_task_row
        storage = MockStorage()

        class FailEnhancer:
            def submit(self, image_url: str) -> str:
                return "tid"

            def poll(self, external_task_id: str) -> EnhanceResult:
                return EnhanceResult(status="failed", error="upstream failed")

        run_beautify_task_sync(
            bty.id,
            lambda: db_session,
            storage=storage,
            enhancer=FailEnhancer(),
        )

        brepo = BeautifyRepository(db_session)
        row = brepo.get_by_id(bty.id)
        assert row.status == "failed"
        assert len(storage.deletes) == 1

    @patch("app.services.beautify_service.runner.BEAUTIFY_TIMEOUT_SECONDS", 0)
    @patch("app.services.beautify_service.runner.BEAUTIFY_POLL_INTERVAL_SECONDS", 0)
    def test_runner_timeout(self, db_session, beautify_task_row):
        bty, _, _ = beautify_task_row
        storage = MockStorage()

        class PendingEnhancer:
            def submit(self, image_url: str) -> str:
                return "tid"

            def poll(self, external_task_id: str) -> EnhanceResult:
                return EnhanceResult(status="running")

        run_beautify_task_sync(
            bty.id,
            lambda: db_session,
            storage=storage,
            enhancer=PendingEnhancer(),
        )

        row = BeautifyRepository(db_session).get_by_id(bty.id)
        assert row.status == "failed"
        assert "超时" in (row.error_message or "")
        assert len(storage.deletes) == 1
