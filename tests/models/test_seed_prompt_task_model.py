import uuid

from app.models.material import (
    MaterialCharacter,
    MaterialCreativeDirection,
    MaterialSeedPromptTask,
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


def test_create_seed_task_row_with_required_fields(db_session):
    char = _make_character(db_session)
    task_id = str(uuid.uuid4())
    task = MaterialSeedPromptTask(
        id=task_id,
        character_id=char.id,
        status="pending",
        creative_direction_id="dir-1",
    )
    db_session.add(task)
    db_session.commit()

    loaded = db_session.query(MaterialSeedPromptTask).filter_by(id=task_id).first()
    assert loaded is not None
    assert loaded.character_id == char.id
    assert loaded.status == "pending"
    assert loaded.creative_direction_id == "dir-1"


def test_cascade_delete_character_removes_seed_tasks(db_session):
    char = _make_character(db_session)
    task = MaterialSeedPromptTask(
        id=str(uuid.uuid4()),
        character_id=char.id,
        status="completed",
    )
    db_session.add(task)
    db_session.commit()

    db_session.delete(char)
    db_session.commit()

    assert (
        db_session.query(MaterialSeedPromptTask)
        .filter_by(character_id=char.id)
        .count()
        == 0
    )


def test_no_unique_on_character_id(db_session):
    char = _make_character(db_session)
    t1 = MaterialSeedPromptTask(
        id=str(uuid.uuid4()),
        character_id=char.id,
        status="pending",
    )
    t2 = MaterialSeedPromptTask(
        id=str(uuid.uuid4()),
        character_id=char.id,
        status="processing",
    )
    db_session.add_all([t1, t2])
    db_session.commit()

    count = (
        db_session.query(MaterialSeedPromptTask)
        .filter_by(character_id=char.id)
        .count()
    )
    assert count == 2


def test_creative_direction_id_nullable(db_session):
    char = _make_character(db_session)
    t_none = MaterialSeedPromptTask(
        id=str(uuid.uuid4()),
        character_id=char.id,
        status="pending",
        creative_direction_id=None,
    )
    t_set = MaterialSeedPromptTask(
        id=str(uuid.uuid4()),
        character_id=char.id,
        status="pending",
        creative_direction_id="some-dir",
    )
    db_session.add_all([t_none, t_set])
    db_session.commit()

    loaded_none = db_session.query(MaterialSeedPromptTask).filter_by(id=t_none.id).first()
    loaded_set = db_session.query(MaterialSeedPromptTask).filter_by(id=t_set.id).first()
    assert loaded_none.creative_direction_id is None
    assert loaded_set.creative_direction_id == "some-dir"


def test_seed_task_creative_direction_id_set_null_on_direction_delete(db_session):
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
    task = MaterialSeedPromptTask(
        id=task_id,
        character_id=char.id,
        status="completed",
        creative_direction_id=direction_id,
    )
    db_session.add_all([direction, task])
    db_session.commit()

    db_session.delete(direction)
    db_session.commit()

    loaded_task = db_session.query(MaterialSeedPromptTask).filter_by(id=task_id).first()
    assert loaded_task is not None
    assert loaded_task.creative_direction_id is None
