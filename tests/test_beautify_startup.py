"""启动时美化 inflight 任务失败化。"""

import uuid

import pytest
from sqlalchemy.orm import sessionmaker

from app.repositories.beautify_repository import BeautifyRepository
from app.services import startup_image_tasks
from app.utils.beautify_timeout import BEAUTIFY_RESTART_ERROR_MESSAGE


def test_startup_fails_inflight_beautify_tasks(db_session, monkeypatch):
    test_session_factory = sessionmaker(bind=db_session.get_bind())
    monkeypatch.setattr(startup_image_tasks, "SessionLocal", test_session_factory)

    repo = BeautifyRepository(db_session)
    task_id = f"bty_{uuid.uuid4().hex[:12]}"
    repo.create(
        {
            "id": task_id,
            "source_kind": "quick_create",
            "source_task_id": "qcreate_fake",
            "source_image_path": "a.png",
            "status": "processing",
            "current_step": "polling",
        }
    )

    counts = startup_image_tasks.run_fail_inflight_image_generation_tasks()
    assert counts["beautify"] >= 1

    row = repo.get_by_id(task_id)
    assert row.status == "failed"
    assert row.error_message == BEAUTIFY_RESTART_ERROR_MESSAGE
    assert row.current_step is None
