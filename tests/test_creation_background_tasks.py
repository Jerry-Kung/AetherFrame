import json
from fastapi import BackgroundTasks
from unittest.mock import patch


def _create_character_with_profile(db_session, character_id: str) -> None:
    from app.repositories.material_repository import MaterialCharacterRepository

    mrepo = MaterialCharacterRepository(db_session)
    mrepo.create(
        {
            "id": character_id,
            "name": "测试角色",
            "bio_json": json.dumps({"chara_profile": "勇敢少女，银发蓝瞳"}, ensure_ascii=False),
        }
    )


def _create_precreation_result(db_session, character_id: str) -> None:
    from app.repositories.creation_repository import CreationPromptPrecreationRepository

    prepo = CreationPromptPrecreationRepository(db_session)
    task = prepo.create(
        character_id=character_id,
        seed_prompt="seed",
        n=2,
        status="completed",
    )
    prepo.update(
        task.id,
        {
            "status": "completed",
            "result_json": [
                {
                    "id": "p1",
                    "title": "t1",
                    "preview": "pv1",
                    "fullPrompt": "prompt body 1",
                    "tags": [],
                    "createdAt": "2026-01-01",
                }
            ],
        },
    )


def _create_five_standard_refs(character_id: str) -> None:
    import os
    from app.services.material_service.material_file_service import get_standard_photo_slot_dir

    slot_dir = get_standard_photo_slot_dir(character_id)
    os.makedirs(slot_dir, exist_ok=True)
    for shot_type in ("full_front", "full_side", "half_front", "half_side", "face_close"):
        with open(os.path.join(slot_dir, f"{shot_type}.png"), "wb") as f:
            f.write(b"png")


@patch("app.services.creation_service.prompt_precreation_service.run_prompt_precreation_task_sync")
def test_prompt_precreation_uses_background_tasks(mock_run_sync, db_session, temp_data_dir):
    from app.services.creation_service.prompt_precreation_service import PromptPrecreationService

    character_id = "mchar_bg_prompt"
    _create_character_with_profile(db_session, character_id)
    service = PromptPrecreationService(db_session)
    background_tasks = BackgroundTasks()

    start = service.start_prompt_precreation(
        character_id=character_id,
        seed_prompt="在海边散步",
        count=2,
        background_tasks=background_tasks,
    )

    assert start["task_id"]
    assert len(background_tasks.tasks) == 1
    mock_run_sync.assert_not_called()


@patch("app.services.creation_service.quick_create_service.run_quick_create_task_sync")
def test_quick_create_uses_background_tasks(mock_run_sync, db_session, temp_data_dir):
    from app.services.creation_service.quick_create_service import QuickCreateService

    character_id = "mchar_bg_quick"
    _create_character_with_profile(db_session, character_id)
    _create_precreation_result(db_session, character_id)
    _create_five_standard_refs(character_id)
    service = QuickCreateService(db_session)
    background_tasks = BackgroundTasks()

    start = service.start_quick_create(
        character_id=character_id,
        selected_prompts=[{"id": "p1", "fullPrompt": "prompt body 1"}],
        n=1,
        aspect_ratio="1:1",
        background_tasks=background_tasks,
    )

    assert start["task_id"]
    assert len(background_tasks.tasks) == 1
    mock_run_sync.assert_not_called()
