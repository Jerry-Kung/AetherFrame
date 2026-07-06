import json
import uuid
from unittest.mock import patch

import pytest
from starlette.datastructures import UploadFile

from app.models.creation import CreationPromptPrecreationTask
from app.models.creation_batch import CreationBatchRunItem
from app.models.material import MaterialCharacter, MaterialCreativeDirection
from app.services.creation_service.batch_automation_service import BatchAutomationService
from app.services.material_service.material_service import MaterialService


def _setup_done_character(db_session, sample_image, *, seeds: dict, char_name: str = "BatchDir"):
    ms = MaterialService(db_session)
    char = ms.create_character(char_name)
    ms.update_setting_text(char.id, "角色设定说明")
    sample_image.seek(0)
    ms.upload_raw_images(
        char.id,
        [UploadFile(filename="r.png", file=sample_image)],
        [["立绘"]],
    )
    urls = [f"https://slot{i}.example/s.png" for i in range(5)]
    bio = {"chara_profile": "# 小档案\n正文", "official_seed_prompts": seeds}
    ms.repo.update(
        char.id,
        {
            "official_photos_json": json.dumps(urls, ensure_ascii=False),
            "bio_json": json.dumps(bio, ensure_ascii=False),
        },
    )
    ms._after_character_material_changed(char.id)
    assert ms.get_character(char.id).status == "done"
    return char


@patch("app.services.creation_service.prompt_precreation_service.run_prompt_precreation_task_sync")
def test_batch_item_persists_seed_dir_id(mock_run, db_session, sample_image):
    dir_id = str(uuid.uuid4())
    char = _setup_done_character(
        db_session,
        sample_image,
        seeds={
            "character_specific": [
                {
                    "id": "s-bound",
                    "text": "绑定种子",
                    "used": False,
                    "creative_direction_id": dir_id,
                },
                {"id": "s-other", "text": "另一条", "used": False},
            ],
            "general": [],
        },
    )
    db_session.add(
        MaterialCreativeDirection(
            id=dir_id,
            character_id=char.id,
            title="方向",
            description="## 核心主题\nx",
            divergence="low",
        )
    )
    db_session.commit()

    MaterialService(db_session).clear_fixed_seed_templates()
    svc = BatchAutomationService(db_session)
    out = svc.start_run(
        iterations=2,
        prompt_count=1,
        images_per_prompt=1,
        aspect_ratio="1:1",
        max_prompts=1,
        character_ids=[char.id],
    )
    items = db_session.query(CreationBatchRunItem).filter_by(run_id=out["run_id"]).all()
    bound = [it for it in items if it.seed_prompt_id == "s-bound"]
    assert len(bound) == 1
    assert bound[0].seed_creative_direction_id == dir_id


def test_batch_item_persists_null_dir_id(db_session, sample_image):
    char = _setup_done_character(
        db_session,
        sample_image,
        seeds={
            "character_specific": [
                {"id": "s-plain", "text": "无方向种子", "used": False, "creative_direction_id": None}
            ],
            "general": [{"id": "g1", "text": "通用种子", "used": False}],
        },
        char_name="BatchNoDir",
    )
    MaterialService(db_session).clear_fixed_seed_templates()
    svc = BatchAutomationService(db_session)
    out = svc.start_run(
        iterations=2,
        prompt_count=1,
        images_per_prompt=1,
        aspect_ratio="1:1",
        max_prompts=1,
        character_ids=[char.id],
    )
    items = db_session.query(CreationBatchRunItem).filter_by(run_id=out["run_id"]).all()
    for it in items:
        assert it.seed_creative_direction_id is None


@patch("app.services.creation_service.prompt_precreation_service.run_prompt_precreation_task_sync")
def test_downstream_prompt_precreation_task_has_markdown(
    mock_run, db_session, sample_image
):
    dir_id = str(uuid.uuid4())
    char = _setup_done_character(
        db_session,
        sample_image,
        seeds={
            "character_specific": [
                {
                    "id": "s1",
                    "text": "种子甲",
                    "used": False,
                    "creative_direction_id": dir_id,
                },
                {"id": "s2", "text": "种子乙", "used": False},
            ],
            "general": [],
        },
        char_name="BatchMarkdown",
    )
    db_session.add(
        MaterialCreativeDirection(
            id=dir_id,
            character_id=char.id,
            title="方向标题",
            description="方向描述",
            divergence="mid",
        )
    )
    db_session.commit()

    def fake_run(task_id: str) -> None:
        task = db_session.query(CreationPromptPrecreationTask).filter_by(id=task_id).first()
        if task:
            task.status = "completed"
            db_session.commit()

    mock_run.side_effect = fake_run

    ms = MaterialService(db_session)
    ms.clear_fixed_seed_templates()

    svc = BatchAutomationService(db_session)
    out = svc.start_run(
        iterations=2,
        prompt_count=1,
        images_per_prompt=1,
        aspect_ratio="1:1",
        max_prompts=1,
        character_ids=[char.id],
    )
    svc.execute_run(out["run_id"])

    tasks = db_session.query(CreationPromptPrecreationTask).all()
    assert tasks
    bound_tasks = [
        t
        for t in tasks
        if any(
            it.seed_creative_direction_id == dir_id
            for it in db_session.query(CreationBatchRunItem).filter_by(run_id=out["run_id"]).all()
            if it.prompt_precreation_task_id == t.id
        )
    ]
    assert bound_tasks
    assert all("### 创作创意方向" in (t.seed_prompt or "") for t in bound_tasks)


@patch("app.services.creation_service.prompt_precreation_service.run_prompt_precreation_task_sync")
def test_downstream_prompt_precreation_task_no_dir_plain_text(
    mock_run, db_session, sample_image
):
    char = _setup_done_character(
        db_session,
        sample_image,
        seeds={
            "character_specific": [{"id": "s1", "text": "纯文本种子", "used": False}],
            "general": [{"id": "g1", "text": "通用", "used": False}],
        },
        char_name="BatchPlain",
    )

    def fake_run(task_id: str) -> None:
        task = db_session.query(CreationPromptPrecreationTask).filter_by(id=task_id).first()
        if task:
            task.status = "completed"
            db_session.commit()

    mock_run.side_effect = fake_run

    MaterialService(db_session).clear_fixed_seed_templates()
    svc = BatchAutomationService(db_session)
    out = svc.start_run(
        iterations=2,
        prompt_count=1,
        images_per_prompt=1,
        aspect_ratio="1:1",
        max_prompts=1,
        character_ids=[char.id],
    )
    svc.execute_run(out["run_id"])

    run_items = db_session.query(CreationBatchRunItem).filter_by(run_id=out["run_id"]).all()
    plain_tasks = [
        db_session.query(CreationPromptPrecreationTask)
        .filter_by(id=it.prompt_precreation_task_id)
        .first()
        for it in run_items
        if it.seed_creative_direction_id is None and it.prompt_precreation_task_id
    ]
    plain_tasks = [t for t in plain_tasks if t]
    assert plain_tasks
    assert all("### 创作创意方向" not in (t.seed_prompt or "") for t in plain_tasks)
    plain_texts = {it.seed_prompt_text for it in run_items if it.seed_creative_direction_id is None}
    assert plain_texts & {"纯文本种子", "通用"}
