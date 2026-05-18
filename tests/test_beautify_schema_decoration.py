"""美化字段回填到创作/修补响应的测试。"""

import os
import uuid

from app.repositories.beautify_repository import BeautifyRepository
from app.services.beautify_service.decorate import (
    decorate_quick_create_results,
    decorate_repair_result_images,
)


def test_decorate_quick_create_results(db_session):
    task_id = "qcreate_test"
    results = [
        {
            "prompt_id": "p1",
            "generated_images": [{"path": "prompt_1/a.png", "review": None}],
        }
    ]
    repo = BeautifyRepository(db_session)
    repo.create(
        {
            "id": f"bty_{uuid.uuid4().hex[:12]}",
            "source_kind": "quick_create",
            "source_task_id": task_id,
            "source_image_path": "prompt_1/a.png",
            "status": "completed",
            "beautified_filename": "a_beautified.png",
        }
    )

    decorated = decorate_quick_create_results(db_session, task_id, results)
    img = decorated[0]["generated_images"][0]
    assert img["beautify_task_id"].startswith("bty_")
    assert img["beautify_status"] == "completed"
    assert img["beautified_path"] == "prompt_1/a_beautified.png"


def test_decorate_repair_result_images(db_session):
    task_id = "repair_test"
    images = [{"filename": "result_0.png", "url": "/api/repair/tasks/x/images/result/result_0.png"}]
    repo = BeautifyRepository(db_session)
    repo.create(
        {
            "id": f"bty_{uuid.uuid4().hex[:12]}",
            "source_kind": "repair",
            "source_task_id": task_id,
            "source_image_path": "result_0.png",
            "status": "completed",
            "beautified_filename": "result_0_beautified.png",
        }
    )

    decorate_repair_result_images(db_session, task_id, images)
    assert images[0]["beautify_status"] == "completed"
    assert images[0]["beautified_filename"] == "result_0_beautified.png"
