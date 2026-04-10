import os
from unittest.mock import patch

import pytest

def _create_character_and_prompt_task(db_session, character_id: str = "mchar_test_quick") -> None:
    from app.repositories.creation_repository import CreationPromptPrecreationRepository
    from app.repositories.material_repository import MaterialCharacterRepository

    mrepo = MaterialCharacterRepository(db_session)
    mrepo.create({"id": character_id, "name": "测试角色"})

    prepo = CreationPromptPrecreationRepository(db_session)
    task = prepo.create(
        character_id=character_id,
        seed_prompt="seed",
        n=2,
        status="completed",
    )
    cards = [
        {
            "id": "p1",
            "title": "t1",
            "preview": "pv1",
            "fullPrompt": "prompt body 1",
            "tags": [],
            "createdAt": "2026-01-01",
        },
        {
            "id": "p2",
            "title": "t2",
            "preview": "pv2",
            "fullPrompt": "prompt body 2",
            "tags": [],
            "createdAt": "2026-01-01",
        },
    ]
    prepo.update(task.id, {"status": "completed", "result_json": cards})


def _create_five_standard_refs(character_id: str) -> None:
    from app.services.material_service.material_file_service import get_standard_photo_slot_dir

    slot_dir = get_standard_photo_slot_dir(character_id)
    os.makedirs(slot_dir, exist_ok=True)
    for shot_type in ("full_front", "full_side", "half_front", "half_side", "face_close"):
        with open(os.path.join(slot_dir, f"{shot_type}.png"), "wb") as f:
            f.write(b"png")


class TestQuickCreateService:
    @patch("app.services.creation_service.quick_create_service.generate_image_with_nano_banana_pro")
    def test_quick_create_success(self, mock_generate, db_session, temp_data_dir):
        from app.services.creation_service.quick_create_service import QuickCreateService

        _create_character_and_prompt_task(db_session, "mchar_qc_ok")
        _create_five_standard_refs("mchar_qc_ok")

        def _ok(**kwargs):
            output_path = kwargs["output_path"]
            file_name = kwargs["file_name"]
            os.makedirs(output_path, exist_ok=True)
            with open(os.path.join(output_path, file_name), "wb") as f:
                f.write(b"img")
            return True

        mock_generate.side_effect = _ok

        service = QuickCreateService(db_session)
        start = service.start_quick_create(
            character_id="mchar_qc_ok",
            selected_prompts=[{"id": "p1", "fullPrompt": "prompt body 1"}],
            n=2,
            aspect_ratio="1:1",
            background_tasks=None,
        )
        status = service.get_task_status(start["task_id"])
        assert status is not None
        assert status["status"] == "completed"
        assert status["results"] is not None
        assert status["results"][0]["success_count"] == 2
        assert len(status["results"][0]["generated_images"]) == 2

    @patch("app.services.creation_service.quick_create_service.generate_image_with_nano_banana_pro")
    def test_quick_create_retry_limited_by_2n(self, mock_generate, db_session, temp_data_dir):
        from app.services.creation_service.quick_create_service import QuickCreateService

        _create_character_and_prompt_task(db_session, "mchar_qc_retry")
        _create_five_standard_refs("mchar_qc_retry")

        calls = {"count": 0}

        def _fail(**kwargs):
            calls["count"] += 1
            return False

        mock_generate.side_effect = _fail

        service = QuickCreateService(db_session)
        start = service.start_quick_create(
            character_id="mchar_qc_retry",
            selected_prompts=[{"id": "p1", "fullPrompt": "prompt body 1"}],
            n=2,
            aspect_ratio="16:9",
            background_tasks=None,
        )
        status = service.get_task_status(start["task_id"])
        assert status is not None
        assert status["status"] == "failed"
        assert calls["count"] == 4
        assert status["results"] is None

    @patch("app.services.creation_service.quick_create_service.generate_image_with_nano_banana_pro")
    def test_quick_create_default_use_latest_cards(self, mock_generate, db_session, temp_data_dir):
        from app.services.creation_service.quick_create_service import QuickCreateService

        _create_character_and_prompt_task(db_session, "mchar_qc_default")
        _create_five_standard_refs("mchar_qc_default")

        def _ok(**kwargs):
            output_path = kwargs["output_path"]
            file_name = kwargs["file_name"]
            os.makedirs(output_path, exist_ok=True)
            with open(os.path.join(output_path, file_name), "wb") as f:
                f.write(b"img")
            return True

        mock_generate.side_effect = _ok

        service = QuickCreateService(db_session)
        start = service.start_quick_create(
            character_id="mchar_qc_default",
            selected_prompts=[],
            n=1,
            aspect_ratio="3:4",
            background_tasks=None,
        )
        status = service.get_task_status(start["task_id"])
        assert status is not None
        assert status["status"] == "completed"
        assert status["results"] is not None
        assert len(status["results"]) == 2
        assert all(x["success_count"] == 1 for x in status["results"])

    def test_quick_create_invalid_aspect_ratio(self, db_session, temp_data_dir):
        from app.services.creation_service.quick_create_service import QuickCreateService

        _create_character_and_prompt_task(db_session, "mchar_qc_ar")
        _create_five_standard_refs("mchar_qc_ar")
        service = QuickCreateService(db_session)
        with pytest.raises(ValueError, match="aspect_ratio"):
            service.start_quick_create(
                character_id="mchar_qc_ar",
                selected_prompts=[{"id": "p1", "fullPrompt": "prompt body 1"}],
                n=1,
                aspect_ratio="2:1",
                background_tasks=None,
            )

    def test_quick_create_missing_standard_photos(self, db_session, temp_data_dir):
        from app.services.creation_service.quick_create_service import QuickCreateService

        _create_character_and_prompt_task(db_session, "mchar_qc_refs")
        service = QuickCreateService(db_session)
        with pytest.raises(ValueError, match="标准参考图不足 5 张"):
            service.start_quick_create(
                character_id="mchar_qc_refs",
                selected_prompts=[{"id": "p1", "fullPrompt": "prompt body 1"}],
                n=1,
                aspect_ratio="1:1",
                background_tasks=None,
            )
