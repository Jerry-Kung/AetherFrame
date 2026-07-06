import asyncio
import json
import os
import uuid
from contextlib import contextmanager
from unittest.mock import patch

import pytest

from app.models.material import MaterialCharacter, MaterialCreativeDirection, MaterialCreativeDirectionTask
from app.services.material_service import creative_direction_generation_service as svc


def _make_character(db_session, char_id: str | None = None) -> MaterialCharacter:
    cid = char_id or f"mchar_{uuid.uuid4().hex[:10]}"
    row = MaterialCharacter(
        id=cid,
        name="Test",
        display_name="Test",
        status="idle",
        setting_text="",
    )
    db_session.add(row)
    db_session.commit()
    return row


def _make_task(db_session, char_id: str, task_id: str | None = None) -> MaterialCreativeDirectionTask:
    tid = task_id or str(uuid.uuid4())
    task = MaterialCreativeDirectionTask(
        id=tid,
        character_id=char_id,
        status="pending",
        divergence="low",
        initial_input="hint",
    )
    db_session.add(task)
    db_session.commit()
    return task


@contextmanager
def _use_test_bg_session(db_session):
    @contextmanager
    def _factory():
        yield db_session

    with patch.object(svc, "BackgroundSessionLocal", _factory):
        yield


@pytest.fixture
def chara_profile_file(temp_data_dir):
    char_id = f"mchar_{uuid.uuid4().hex[:10]}"
    base = os.path.join(temp_data_dir, "material", "characters", char_id, "chara_profile")
    os.makedirs(base, exist_ok=True)
    path = os.path.join(base, "chara_profile_final.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("# profile")
    return char_id


def test_run_happy_path(db_session, temp_data_dir, chara_profile_file):
    char_id = chara_profile_file
    _make_character(db_session, char_id)
    task = _make_task(db_session, char_id)

    async def _run():
        with _use_test_bg_session(db_session), patch.object(
            svc, "_resolve_chara_profile_text", return_value="# profile"
        ), patch.object(
            svc,
            "yibu_gemini_infer",
            return_value='{"title":"T","description":"D"}',
        ):
            await svc.run_creative_direction_task(task.id)

    asyncio.run(_run())

    db_session.expire_all()
    loaded_task = db_session.query(MaterialCreativeDirectionTask).filter_by(id=task.id).first()
    assert loaded_task.status == "completed"
    assert loaded_task.result_direction_id
    direction = db_session.query(MaterialCreativeDirection).filter_by(
        id=loaded_task.result_direction_id
    ).first()
    assert direction is not None
    assert direction.title == "T"
    assert loaded_task.result_direction_id == direction.id


def test_run_with_fence(db_session, chara_profile_file):
    char_id = chara_profile_file
    _make_character(db_session, char_id)
    task = _make_task(db_session, char_id)

    async def _run():
        with _use_test_bg_session(db_session), patch.object(
            svc, "_resolve_chara_profile_text", return_value="# profile"
        ), patch.object(
            svc,
            "yibu_gemini_infer",
            return_value='```json\n{"title":"T","description":"D"}\n```',
        ):
            await svc.run_creative_direction_task(task.id)

    asyncio.run(_run())
    db_session.expire_all()
    loaded = db_session.query(MaterialCreativeDirectionTask).filter_by(id=task.id).first()
    assert loaded.status == "completed"


def test_run_invalid_json(db_session, chara_profile_file):
    char_id = chara_profile_file
    _make_character(db_session, char_id)
    task = _make_task(db_session, char_id)

    async def _run():
        with _use_test_bg_session(db_session), patch.object(
            svc, "_resolve_chara_profile_text", return_value="# profile"
        ), patch.object(svc, "yibu_gemini_infer", return_value="not json{"):
            await svc.run_creative_direction_task(task.id)

    asyncio.run(_run())
    db_session.expire_all()
    loaded = db_session.query(MaterialCreativeDirectionTask).filter_by(id=task.id).first()
    assert loaded.status == "failed"
    assert "snippet=" in (loaded.error_message or "")
    assert db_session.query(MaterialCreativeDirection).filter_by(character_id=char_id).count() == 0


def test_run_missing_title(db_session, chara_profile_file):
    char_id = chara_profile_file
    _make_character(db_session, char_id)
    task = _make_task(db_session, char_id)

    async def _run():
        with _use_test_bg_session(db_session), patch.object(
            svc, "_resolve_chara_profile_text", return_value="# profile"
        ), patch.object(svc, "yibu_gemini_infer", return_value='{"description":"D"}'):
            await svc.run_creative_direction_task(task.id)

    asyncio.run(_run())
    db_session.expire_all()
    loaded = db_session.query(MaterialCreativeDirectionTask).filter_by(id=task.id).first()
    assert loaded.status == "failed"
    assert "missing 'title'" in (loaded.error_message or "")


def test_run_chara_profile_missing(db_session):
    char_id = f"mchar_{uuid.uuid4().hex[:10]}"
    _make_character(db_session, char_id)
    task = _make_task(db_session, char_id)

    async def _run():
        with _use_test_bg_session(db_session):
            await svc.run_creative_direction_task(task.id)

    asyncio.run(_run())
    db_session.expire_all()
    loaded = db_session.query(MaterialCreativeDirectionTask).filter_by(id=task.id).first()
    assert loaded.status == "failed"
    assert db_session.query(MaterialCreativeDirection).filter_by(character_id=char_id).count() == 0


def test_run_file_write_failure_does_not_rollback_db(db_session, chara_profile_file):
    char_id = chara_profile_file
    _make_character(db_session, char_id)
    task = _make_task(db_session, char_id)

    async def _run():
        with _use_test_bg_session(db_session), patch.object(
            svc, "_resolve_chara_profile_text", return_value="# profile"
        ), patch.object(
            svc,
            "yibu_gemini_infer",
            return_value='{"title":"T","description":"D"}',
        ), patch.object(svc, "_write_direction_json_file", side_effect=OSError("disk")):
            await svc.run_creative_direction_task(task.id)

    asyncio.run(_run())
    db_session.expire_all()
    loaded = db_session.query(MaterialCreativeDirectionTask).filter_by(id=task.id).first()
    assert loaded.status == "completed"
    assert loaded.result_direction_id
