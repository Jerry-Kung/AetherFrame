import asyncio
import json
import os
import uuid
from contextlib import contextmanager
from unittest.mock import patch

import pytest

from app.models.material import (
    MaterialCharacter,
    MaterialCreativeDirection,
    MaterialSeedPromptTask,
)
from app.services.material_service import seed_prompt_generation_service as svc


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


def _make_seed_task(
    db_session,
    char_id: str,
    task_id: str | None = None,
    creative_direction_id: str | None = None,
) -> MaterialSeedPromptTask:
    tid = task_id or str(uuid.uuid4())
    task = MaterialSeedPromptTask(
        id=tid,
        character_id=char_id,
        status="pending",
        creative_direction_id=creative_direction_id,
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


def test_run_happy_path_no_direction(db_session, temp_data_dir, chara_profile_file):
    char_id = chara_profile_file
    _make_character(db_session, char_id)
    task = _make_seed_task(db_session, char_id)

    async def _run():
        with _use_test_bg_session(db_session), patch.object(
            svc, "_resolve_chara_profile_text", return_value="# profile"
        ), patch.object(
            svc,
            "yibu_gemini_infer",
            return_value='{"character_specific":["seed1","seed2"]}',
        ):
            await svc.run_seed_prompt_task(task.id)

    asyncio.run(_run())

    db_session.expire_all()
    loaded = db_session.query(MaterialSeedPromptTask).filter_by(id=task.id).first()
    assert loaded.status == "completed"
    draft = svc.read_seed_draft_file(char_id, task.id)
    assert draft is not None
    assert draft["character_specific"] == ["seed1", "seed2"]


def test_run_happy_path_with_direction(db_session, temp_data_dir, chara_profile_file):
    char_id = chara_profile_file
    _make_character(db_session, char_id)
    direction_id = str(uuid.uuid4())
    direction = MaterialCreativeDirection(
        id=direction_id,
        character_id=char_id,
        title="My Title",
        description="My Desc",
        divergence="low",
    )
    db_session.add(direction)
    db_session.commit()
    task = _make_seed_task(db_session, char_id, creative_direction_id=direction_id)

    captured = {}

    def _fake_infer(prompt, **kwargs):
        captured["prompt"] = prompt
        return '{"character_specific":["bound-seed"]}'

    async def _run():
        with _use_test_bg_session(db_session), patch.object(
            svc, "_resolve_chara_profile_text", return_value="# profile"
        ), patch.object(svc, "yibu_gemini_infer", side_effect=_fake_infer):
            await svc.run_seed_prompt_task(task.id)

    asyncio.run(_run())

    assert "My Title" in captured.get("prompt", "")
    assert "My Desc" in captured.get("prompt", "")
    loaded = db_session.query(MaterialSeedPromptTask).filter_by(id=task.id).first()
    assert loaded.status == "completed"


def test_run_invalid_direction_falls_back(db_session, temp_data_dir, chara_profile_file):
    char_id = chara_profile_file
    _make_character(db_session, char_id)
    task = _make_seed_task(db_session, char_id, creative_direction_id="missing-dir")

    captured = {}

    def _fake_infer(prompt, **kwargs):
        captured["prompt"] = prompt
        return '{"character_specific":["seed"]}'

    async def _run():
        with _use_test_bg_session(db_session), patch.object(
            svc, "_resolve_chara_profile_text", return_value="# profile"
        ), patch.object(svc, "yibu_gemini_infer", side_effect=_fake_infer):
            await svc.run_seed_prompt_task(task.id)

    asyncio.run(_run())

    assert svc.FALLBACK_DIRECTION_TEXT in captured.get("prompt", "")
    loaded = db_session.query(MaterialSeedPromptTask).filter_by(id=task.id).first()
    assert loaded.status == "completed"


def test_run_cross_character_direction_falls_back(db_session, temp_data_dir, chara_profile_file):
    char_id = chara_profile_file
    other_id = f"mchar_{uuid.uuid4().hex[:10]}"
    _make_character(db_session, char_id)
    _make_character(db_session, other_id)
    direction_id = str(uuid.uuid4())
    direction = MaterialCreativeDirection(
        id=direction_id,
        character_id=other_id,
        title="Other",
        description="Other",
        divergence="low",
    )
    db_session.add(direction)
    db_session.commit()
    task = _make_seed_task(db_session, char_id, creative_direction_id=direction_id)

    async def _run():
        with _use_test_bg_session(db_session), patch.object(
            svc, "_resolve_chara_profile_text", return_value="# profile"
        ), patch.object(
            svc,
            "yibu_gemini_infer",
            return_value='{"character_specific":["seed"]}',
        ):
            await svc.run_seed_prompt_task(task.id)

    asyncio.run(_run())

    loaded = db_session.query(MaterialSeedPromptTask).filter_by(id=task.id).first()
    assert loaded.status == "completed"


def test_run_invalid_json_fails_task(db_session, temp_data_dir, chara_profile_file):
    char_id = chara_profile_file
    _make_character(db_session, char_id)
    task = _make_seed_task(db_session, char_id)

    async def _run():
        with _use_test_bg_session(db_session), patch.object(
            svc, "_resolve_chara_profile_text", return_value="# profile"
        ), patch.object(svc, "yibu_gemini_infer", return_value="not json {{"):
            await svc.run_seed_prompt_task(task.id)

    asyncio.run(_run())

    loaded = db_session.query(MaterialSeedPromptTask).filter_by(id=task.id).first()
    assert loaded.status == "failed"
    assert "snippet" in (loaded.error_message or "")


def test_run_missing_character_specific(db_session, temp_data_dir, chara_profile_file):
    char_id = chara_profile_file
    _make_character(db_session, char_id)
    task = _make_seed_task(db_session, char_id)

    async def _run():
        with _use_test_bg_session(db_session), patch.object(
            svc, "_resolve_chara_profile_text", return_value="# profile"
        ), patch.object(
            svc, "yibu_gemini_infer", return_value='{"general":["x"]}',
        ):
            await svc.run_seed_prompt_task(task.id)

    asyncio.run(_run())

    loaded = db_session.query(MaterialSeedPromptTask).filter_by(id=task.id).first()
    assert loaded.status == "failed"
    assert "missing" in (loaded.error_message or "").lower()


def test_run_empty_character_specific(db_session, temp_data_dir, chara_profile_file):
    char_id = chara_profile_file
    _make_character(db_session, char_id)
    task = _make_seed_task(db_session, char_id)

    async def _run():
        with _use_test_bg_session(db_session), patch.object(
            svc, "_resolve_chara_profile_text", return_value="# profile"
        ), patch.object(
            svc, "yibu_gemini_infer", return_value='{"character_specific":[]}',
        ):
            await svc.run_seed_prompt_task(task.id)

    asyncio.run(_run())

    loaded = db_session.query(MaterialSeedPromptTask).filter_by(id=task.id).first()
    assert loaded.status == "failed"


def test_run_file_write_failure_marks_failed(db_session, temp_data_dir, chara_profile_file):
    char_id = chara_profile_file
    _make_character(db_session, char_id)
    task = _make_seed_task(db_session, char_id)

    async def _run():
        with _use_test_bg_session(db_session), patch.object(
            svc, "_resolve_chara_profile_text", return_value="# profile"
        ), patch.object(
            svc,
            "yibu_gemini_infer",
            return_value='{"character_specific":["seed"]}',
        ), patch.object(svc, "_write_seed_draft_file", return_value=False):
            await svc.run_seed_prompt_task(task.id)

    asyncio.run(_run())

    loaded = db_session.query(MaterialSeedPromptTask).filter_by(id=task.id).first()
    assert loaded.status == "failed"


def test_read_seed_draft_file_after_write(db_session, temp_data_dir, chara_profile_file):
    char_id = chara_profile_file
    task_id = str(uuid.uuid4())
    svc._write_seed_draft_file(char_id, task_id, ["a", "b"])
    data = svc.read_seed_draft_file(char_id, task_id)
    assert data == {"character_specific": ["a", "b"]}


def test_read_seed_draft_file_missing_returns_none(temp_data_dir):
    char_id = f"mchar_{uuid.uuid4().hex[:10]}"
    assert svc.read_seed_draft_file(char_id, "missing-task") is None
