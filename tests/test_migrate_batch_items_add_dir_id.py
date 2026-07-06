import json
import uuid

from sqlalchemy import text

from app.models.creation_batch import CreationBatchRunItem
from app.models.database import engine, migrate_creation_batch_run_items_add_seed_dir_id
from app.models.material import MaterialCharacter


def _column_names() -> set[str]:
    with engine.connect() as conn:
        cols = conn.execute(text("PRAGMA table_info(creation_batch_run_items)")).fetchall()
        return {c[1] for c in cols}


def test_migrate_adds_column(db_session):
    migrate_creation_batch_run_items_add_seed_dir_id()
    assert "seed_creative_direction_id" in _column_names()


def test_migrate_idempotent(db_session):
    migrate_creation_batch_run_items_add_seed_dir_id()
    migrate_creation_batch_run_items_add_seed_dir_id()


def test_existing_rows_have_null_after_migrate(db_session):
    run_id = f"bb_run_{uuid.uuid4().hex[:12]}"
    item_id = f"bb_item_{uuid.uuid4().hex[:12]}"
    char_id = f"mchar_{uuid.uuid4().hex[:10]}"
    db_session.add(
        MaterialCharacter(
            id=char_id,
            name="M",
            display_name="M",
            status="idle",
            setting_text="",
        )
    )
    db_session.commit()
    db_session.execute(
        text(
            "INSERT INTO creation_batch_runs (id, status, iterations_total, iterations_done, config_json) "
            "VALUES (:id, 'pending', 2, 0, '{}')"
        ),
        {"id": run_id},
    )
    db_session.execute(
        text(
            "INSERT INTO creation_batch_run_items "
            "(id, run_id, step_index, character_id, seed_prompt_id, seed_section, seed_prompt_text, status) "
            "VALUES (:id, :run_id, 0, :cid, 's1', 'general', 'text', 'pending')"
        ),
        {"id": item_id, "run_id": run_id, "cid": char_id},
    )
    db_session.commit()

    migrate_creation_batch_run_items_add_seed_dir_id()

    row = db_session.query(CreationBatchRunItem).filter_by(id=item_id).first()
    assert row is not None
    assert row.seed_creative_direction_id is None
