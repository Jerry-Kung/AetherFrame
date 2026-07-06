import uuid
from datetime import datetime, timedelta, timezone

from app.models.material import MaterialCharacter, MaterialCreativeDirectionTask, MaterialSeedPromptTask
from app.services.material_service.cleanup import cleanup_old_material_tasks


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


def test_cleanup_removes_old_terminal(db_session):
    char = _make_character(db_session)
    old = datetime.now(timezone.utc) - timedelta(days=31)
    db_session.add(
        MaterialCreativeDirectionTask(
            id=str(uuid.uuid4()),
            character_id=char.id,
            status="completed",
            divergence="low",
            created_at=old,
        )
    )
    db_session.commit()
    n = cleanup_old_material_tasks(db_session)
    assert n == 1
    assert db_session.query(MaterialCreativeDirectionTask).count() == 0


def test_cleanup_keeps_old_inflight(db_session):
    char = _make_character(db_session)
    old = datetime.now(timezone.utc) - timedelta(days=31)
    db_session.add(
        MaterialCreativeDirectionTask(
            id=str(uuid.uuid4()),
            character_id=char.id,
            status="processing",
            divergence="low",
            created_at=old,
        )
    )
    db_session.commit()
    n = cleanup_old_material_tasks(db_session)
    assert n == 0
    assert db_session.query(MaterialCreativeDirectionTask).count() == 1


def test_cleanup_keeps_recent_terminal(db_session):
    char = _make_character(db_session)
    recent = datetime.now(timezone.utc) - timedelta(days=29)
    db_session.add(
        MaterialCreativeDirectionTask(
            id=str(uuid.uuid4()),
            character_id=char.id,
            status="completed",
            divergence="low",
            created_at=recent,
        )
    )
    db_session.commit()
    n = cleanup_old_material_tasks(db_session)
    assert n == 0


def test_cleanup_returns_zero_when_nothing(db_session):
    assert cleanup_old_material_tasks(db_session) == 0


def test_cleanup_removes_old_seed_tasks(db_session):
    char = _make_character(db_session)
    old = datetime.now(timezone.utc) - timedelta(days=31)
    db_session.add(
        MaterialSeedPromptTask(
            id=str(uuid.uuid4()),
            character_id=char.id,
            status="completed",
            created_at=old,
        )
    )
    db_session.commit()
    n = cleanup_old_material_tasks(db_session)
    assert n == 1
    assert db_session.query(MaterialSeedPromptTask).count() == 0


def test_cleanup_keeps_recent_seed_tasks(db_session):
    char = _make_character(db_session)
    recent = datetime.now(timezone.utc) - timedelta(days=29)
    db_session.add(
        MaterialSeedPromptTask(
            id=str(uuid.uuid4()),
            character_id=char.id,
            status="failed",
            created_at=recent,
        )
    )
    db_session.commit()
    n = cleanup_old_material_tasks(db_session)
    assert n == 0
    assert db_session.query(MaterialSeedPromptTask).count() == 1


def test_cleanup_returns_total_from_both_tables(db_session):
    char = _make_character(db_session)
    old = datetime.now(timezone.utc) - timedelta(days=31)
    db_session.add(
        MaterialCreativeDirectionTask(
            id=str(uuid.uuid4()),
            character_id=char.id,
            status="completed",
            divergence="low",
            created_at=old,
        )
    )
    db_session.add_all(
        [
            MaterialSeedPromptTask(
                id=str(uuid.uuid4()),
                character_id=char.id,
                status="completed",
                created_at=old,
            ),
            MaterialSeedPromptTask(
                id=str(uuid.uuid4()),
                character_id=char.id,
                status="failed",
                created_at=old,
            ),
        ]
    )
    db_session.commit()
    n = cleanup_old_material_tasks(db_session)
    assert n == 3
