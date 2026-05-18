"""删除上游任务时级联清理美化记录与云对象。"""

import os
import uuid
from unittest.mock import patch

import pytest

from app.models.creation import CreationQuickCreateTask  # noqa: F401
from app.models.material import MaterialCharacter  # noqa: F401
from app.repositories.beautify_repository import BeautifyRepository
from app.repositories.creation_repository import CreationQuickCreateRepository
from app.schemas.repair import TaskCreate
from app.services.creation_service.batch_automation_service import BatchAutomationService
from app.services.creation_service.quick_create_service import QuickCreateService
from app.services.repair_service import RepairService
from tests.test_beautify_service import MockStorage


def _create_completed_beautify_row(
    db_session,
    *,
    source_kind: str,
    source_task_id: str,
    source_image_path: str,
    cloud_key: str = "beautify/test/object.png",
) -> str:
    row_id = f"bty_{uuid.uuid4().hex[:12]}"
    BeautifyRepository(db_session).create(
        {
            "id": row_id,
            "source_kind": source_kind,
            "source_task_id": source_task_id,
            "source_image_path": source_image_path,
            "status": "completed",
            "cloud_object_key": cloud_key,
        }
    )
    return row_id


@pytest.fixture
def quick_create_with_image(db_session):
    mrepo = __import__(
        "app.repositories.material_repository", fromlist=["MaterialCharacterRepository"]
    ).MaterialCharacterRepository(db_session)
    char_id = f"mchar_{uuid.uuid4().hex[:12]}"
    char = mrepo.create({"id": char_id, "name": "cascade-test-char"})
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
    with open(os.path.join(img_dir, "out.png"), "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
    return task, img_rel


@patch("app.tools.beautify.storage.get_default_client")
def test_delete_quick_create_history_cleans_beautify(
    mock_get_client, db_session, quick_create_with_image
):
    storage = MockStorage()
    mock_get_client.return_value = storage
    task, img_rel = quick_create_with_image
    cloud_key = "beautify/qc/obj.png"
    _create_completed_beautify_row(
        db_session,
        source_kind="quick_create",
        source_task_id=task.id,
        source_image_path=img_rel,
        cloud_key=cloud_key,
    )
    work_dir = task.work_dir

    QuickCreateService(db_session).delete_history(task.id)

    assert BeautifyRepository(db_session).list_by_source("quick_create", task.id) == []
    assert cloud_key in storage.deletes
    assert not os.path.exists(work_dir)


@patch("app.tools.beautify.storage.get_default_client")
def test_delete_quick_create_cleanup_before_rmtree(
    mock_get_client, db_session, quick_create_with_image
):
    storage = MockStorage()
    mock_get_client.return_value = storage
    task, img_rel = quick_create_with_image
    _create_completed_beautify_row(
        db_session,
        source_kind="quick_create",
        source_task_id=task.id,
        source_image_path=img_rel,
    )
    call_order: list[str] = []
    from app.services.beautify_service import BeautifyService

    original = BeautifyService.cleanup_for_quick_create_task

    def tracked_cleanup(self, task_id: str) -> int:
        call_order.append("cleanup")
        return original(self, task_id)

    with patch.object(BeautifyService, "cleanup_for_quick_create_task", tracked_cleanup):
        with patch(
            "app.services.creation_service.quick_create_service.shutil.rmtree",
            side_effect=lambda *a, **k: call_order.append("rmtree"),
        ):
            QuickCreateService(db_session).delete_history(task.id)

    assert call_order.index("cleanup") < call_order.index("rmtree")


@patch("app.tools.beautify.storage.get_default_client")
def test_delete_batch_item_cleans_beautify(mock_get_client, db_session, quick_create_with_image):
    storage = MockStorage()
    mock_get_client.return_value = storage
    task, img_rel = quick_create_with_image
    cloud_key = "beautify/batch/obj.png"
    _create_completed_beautify_row(
        db_session,
        source_kind="quick_create",
        source_task_id=task.id,
        source_image_path=img_rel,
        cloud_key=cloud_key,
    )
    from app.repositories.creation_batch_repository import CreationBatchRepository

    batch_repo = CreationBatchRepository(db_session)
    run = batch_repo.create_run(
        iterations_total=1,
        config_json="{}",
        status="completed",
    )
    item = batch_repo.create_item(
        run_id=run.id,
        step_index=0,
        character_id=task.character_id,
        seed_prompt_id="s1",
        seed_section="general",
        seed_prompt_text="seed",
        status="completed",
    )
    batch_repo.update_item(item.id, {"quick_create_task_id": task.id})

    BatchAutomationService(db_session).delete_batch_item(item.id)

    assert BeautifyRepository(db_session).list_by_source("quick_create", task.id) == []
    assert cloud_key in storage.deletes


@patch("app.tools.beautify.storage.get_default_client")
def test_delete_repair_task_cleans_beautify(mock_get_client, db_session):
    storage = MockStorage()
    mock_get_client.return_value = storage
    service = RepairService(db_session)
    task = service.create_task(TaskCreate(name="cascade", prompt="p", output_count=1))
    cloud_key = "beautify/repair/obj.png"
    img_rel = "result_1.png"
    _create_completed_beautify_row(
        db_session,
        source_kind="repair",
        source_task_id=task.id,
        source_image_path=img_rel,
        cloud_key=cloud_key,
    )

    call_order: list[str] = []
    from app.services.beautify_service import BeautifyService

    original = BeautifyService.cleanup_for_repair_task

    def tracked_cleanup(self, task_id: str) -> int:
        call_order.append("cleanup")
        return original(self, task_id)

    from app.services.repair_service import repair_file_service

    original_delete_files = repair_file_service.delete_task_files

    def tracked_delete_files(tid: str) -> bool:
        call_order.append("delete_files")
        return original_delete_files(tid)

    with patch.object(BeautifyService, "cleanup_for_repair_task", tracked_cleanup):
        with patch.object(repair_file_service, "delete_task_files", tracked_delete_files):
            assert service.delete_task(task.id) is True

    assert call_order.index("cleanup") < call_order.index("delete_files")
    assert BeautifyRepository(db_session).list_by_source("repair", task.id) == []
    assert cloud_key in storage.deletes
