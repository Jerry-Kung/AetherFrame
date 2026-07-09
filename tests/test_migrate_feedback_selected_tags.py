"""creation_image_feedbacks.selected_tags_json 迁移 + repo 透传"""

import uuid

from sqlalchemy import text

from app.repositories.creation_feedback_repository import CreationImageFeedbackRepository


def _column_names(db_session) -> set[str]:
    """查询 creation_image_feedbacks 表的列名"""
    conn = db_session.connection()
    cols = conn.execute(text("PRAGMA table_info(creation_image_feedbacks)")).fetchall()
    return {c[1] for c in cols}


def test_migrate_adds_column_and_idempotent(db_session):
    from app.models.database import migrate_creation_image_feedbacks_add_selected_tags
    migrate_creation_image_feedbacks_add_selected_tags()
    assert "selected_tags_json" in _column_names(db_session)
    migrate_creation_image_feedbacks_add_selected_tags()  # 幂等重跑不抛


def test_new_row_defaults_empty_list(db_session):
    repo = CreationImageFeedbackRepository(db_session)
    row = repo.upsert(
        quick_create_task_id=f"qcreate_{uuid.uuid4().hex[:12]}",
        prompt_id="p1", image_index=0,
        leg_foot_bad=False, feedback_text="旧调用不传标签",
    )
    assert row.selected_tags_json == "[]"


def test_upsert_roundtrips_selected_tags_json(db_session):
    repo = CreationImageFeedbackRepository(db_session)
    tid = f"qcreate_{uuid.uuid4().hex[:12]}"
    payload = '[{"key": "sock_wrinkle_heavy", "severity": "severe"}]'
    row = repo.upsert(
        quick_create_task_id=tid, prompt_id="p1", image_index=0,
        leg_foot_bad=True, feedback_text="", selected_tags_json=payload,
    )
    assert row.selected_tags_json == payload
    # upsert 覆盖更新
    row2 = repo.upsert(
        quick_create_task_id=tid, prompt_id="p1", image_index=0,
        leg_foot_bad=False, feedback_text="", selected_tags_json="[]",
    )
    assert row2.id == row.id
    assert row2.selected_tags_json == "[]"
