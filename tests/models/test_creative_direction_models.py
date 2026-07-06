import uuid

import pytest

from app.models.material import (
    MaterialCharacter,
    MaterialCreativeDirection,
    MaterialCreativeDirectionTask,
)


def _make_character(db_session) -> MaterialCharacter:
    char_id = f"mchar_{uuid.uuid4().hex[:10]}"
    row = MaterialCharacter(
        id=char_id,
        name="Test",
        display_name="Test",
        status="idle",
        setting_text="",
    )
    db_session.add(row)
    db_session.commit()
    return row


def test_create_direction_row_with_required_fields(db_session):
    char = _make_character(db_session)
    task_id = str(uuid.uuid4())
    task = MaterialCreativeDirectionTask(
        id=task_id,
        character_id=char.id,
        status="completed",
        divergence="low",
    )
    db_session.add(task)
    db_session.commit()

    direction_id = str(uuid.uuid4())
    direction = MaterialCreativeDirection(
        id=direction_id,
        character_id=char.id,
        title="Title",
        description="## 核心主题\n主题",
        divergence="low",
        initial_input="hint",
        source_task_id=task_id,
    )
    db_session.add(direction)
    db_session.commit()

    loaded = db_session.query(MaterialCreativeDirection).filter_by(id=direction_id).first()
    assert loaded is not None
    assert loaded.title == "Title"
    assert loaded.description.startswith("##")
    assert loaded.divergence == "low"
    assert loaded.initial_input == "hint"
    assert loaded.source_task_id == task_id


def test_cascade_delete_character_removes_directions(db_session):
    char = _make_character(db_session)
    direction = MaterialCreativeDirection(
        id=str(uuid.uuid4()),
        character_id=char.id,
        title="T",
        description="D",
        divergence="mid",
    )
    db_session.add(direction)
    db_session.commit()

    db_session.delete(char)
    db_session.commit()

    assert (
        db_session.query(MaterialCreativeDirection)
        .filter_by(character_id=char.id)
        .count()
        == 0
    )


def test_direction_task_no_unique_on_character_id(db_session):
    char = _make_character(db_session)
    t1 = MaterialCreativeDirectionTask(
        id=str(uuid.uuid4()),
        character_id=char.id,
        status="pending",
        divergence="low",
    )
    t2 = MaterialCreativeDirectionTask(
        id=str(uuid.uuid4()),
        character_id=char.id,
        status="pending",
        divergence="high",
    )
    db_session.add_all([t1, t2])
    db_session.commit()

    count = (
        db_session.query(MaterialCreativeDirectionTask)
        .filter_by(character_id=char.id)
        .count()
    )
    assert count == 2


def test_direction_task_set_null_on_direction_delete(db_session):
    char = _make_character(db_session)
    direction_id = str(uuid.uuid4())
    task_id = str(uuid.uuid4())
    direction = MaterialCreativeDirection(
        id=direction_id,
        character_id=char.id,
        title="T",
        description="D",
        divergence="low",
    )
    task = MaterialCreativeDirectionTask(
        id=task_id,
        character_id=char.id,
        status="completed",
        divergence="low",
        result_direction_id=direction_id,
    )
    db_session.add_all([direction, task])
    db_session.commit()

    db_session.delete(direction)
    db_session.commit()

    loaded_task = db_session.query(MaterialCreativeDirectionTask).filter_by(id=task_id).first()
    assert loaded_task is not None
    assert loaded_task.result_direction_id is None
