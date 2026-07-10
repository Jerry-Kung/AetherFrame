"""一次性数据迁移：leg_foot_bad 重算为纯标签推导值（app_migrations 守卫）。"""

import uuid

from sqlalchemy import text

from app.repositories.creation_feedback_repository import CreationImageFeedbackRepository
from app.services.creation_service import feedback_tags

FLAG = "2026-07-10_feedback_leg_foot_bad_recompute"

TEST_CFG = {
    "version": 9,
    "tags": [
        {"key": "sock_wrinkle_heavy", "label": "袜子皱褶过于夸张", "polarity": "negative",
         "leg_foot_bad": True, "taxonomy": "袜子/皱褶夸张", "group": "袜子"},
        {"key": "style_doll3d", "label": "3D玩偶感", "polarity": "negative",
         "leg_foot_bad": False, "taxonomy": "画风/3D玩偶感", "group": "画风"},
        {"key": "pos_overall_good", "label": "整体效果好", "polarity": "positive"},
    ],
}


def _seed(db_session, *, text_="", bad=False, tags_json="[]"):
    return CreationImageFeedbackRepository(db_session).upsert(
        quick_create_task_id=f"qcreate_{uuid.uuid4().hex[:12]}",
        prompt_id="p1", image_index=0,
        leg_foot_bad=bad, feedback_text=text_, selected_tags_json=tags_json,
    )


def _run_migration(monkeypatch, cfg=TEST_CFG):
    from app.models import database

    monkeypatch.setattr(feedback_tags, "get_tag_config", lambda: cfg)
    database.migrate_creation_image_feedbacks_recompute_leg_foot_bad()


def _flag_set(db_session) -> bool:
    row = db_session.connection().execute(
        text("SELECT 1 FROM app_migrations WHERE name = :n"), {"n": FLAG}
    ).fetchone()
    return row is not None


def _clear_flag(db_session):
    """自清理：不假设 db_session 是每测试独立库。"""
    from app.models.database import _ensure_app_migrations_table

    _ensure_app_migrations_table()
    conn = db_session.connection()
    conn.execute(text("DELETE FROM app_migrations WHERE name = :n"), {"n": FLAG})
    conn.execute(text("DELETE FROM creation_image_feedbacks"))
    db_session.commit()


def test_recompute_rules_and_cleanup(db_session, monkeypatch):
    _clear_flag(db_session)
    r_text = _seed(db_session, text_="纯文本时代的手动 bad", bad=True)  # → bad 变 False，行保留
    r_bad = _seed(db_session, tags_json='[{"key": "sock_wrinkle_heavy", "severity": "severe"}]')  # → True
    r_style = _seed(db_session, bad=True, tags_json='[{"key": "style_doll3d", "severity": "minor"}]')  # → False
    r_empty = _seed(db_session, bad=True)  # 文本空+无标签 → 删除
    r_empty_id = r_empty.id  # 迁移会删该行，读取后 ORM 对象会被 expire_all 标记失效，先取好 id
    _run_migration(monkeypatch)
    db_session.expire_all()
    rows = {r.id: r for r in CreationImageFeedbackRepository(db_session).list_all()}
    assert r_empty_id not in rows
    assert rows[r_text.id].leg_foot_bad is False
    assert rows[r_bad.id].leg_foot_bad is True
    assert rows[r_style.id].leg_foot_bad is False
    assert _flag_set(db_session)


def test_flag_makes_it_run_once(db_session, monkeypatch):
    _clear_flag(db_session)
    _run_migration(monkeypatch)  # 空库跑一遍，置标记
    assert _flag_set(db_session)
    row = _seed(db_session, bad=True)  # 标记已置，重跑不得再动数据
    _run_migration(monkeypatch)
    db_session.expire_all()
    got = CreationImageFeedbackRepository(db_session).list_all()
    assert [r.id for r in got] == [row.id]
    assert got[0].leg_foot_bad is True


def test_empty_config_skips_without_flag(db_session, monkeypatch):
    _clear_flag(db_session)
    _seed(db_session, text_="有文本", bad=True)
    _run_migration(monkeypatch, cfg={"version": 0, "tags": []})
    assert not _flag_set(db_session)  # 不置标记，下次启动重试
    db_session.expire_all()
    got = CreationImageFeedbackRepository(db_session).list_all()
    assert got[0].leg_foot_bad is True  # 数据未动


def test_corrupt_tags_json_treated_as_empty(db_session, monkeypatch):
    _clear_flag(db_session)
    kept = _seed(db_session, text_="有文本", bad=True, tags_json="{broken")  # → False，保留
    gone = _seed(db_session, bad=True, tags_json="{broken")  # 解析失败视为无标签且无文本 → 删除
    gone_id = gone.id  # 迁移会删该行，读取后 ORM 对象会被 expire_all 标记失效，先取好 id
    _run_migration(monkeypatch)
    db_session.expire_all()
    ids = {r.id for r in CreationImageFeedbackRepository(db_session).list_all()}
    assert kept.id in ids and gone_id not in ids
