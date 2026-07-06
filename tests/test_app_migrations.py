from sqlalchemy import text

from app.models.database import (
    _ensure_app_migrations_table,
    _is_migration_applied,
    _mark_migration_applied,
    engine,
)


def test_ensure_table_idempotent():
    _ensure_app_migrations_table()
    _ensure_app_migrations_table()


def test_is_migration_applied_default_false():
    _ensure_app_migrations_table()
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM app_migrations WHERE name = 'test_flag_xyz'"))
        conn.commit()
        assert _is_migration_applied(conn, "test_flag_xyz") is False


def test_mark_then_is_applied_returns_true():
    _ensure_app_migrations_table()
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM app_migrations WHERE name = 'test_flag_mark'"))
        conn.commit()
        assert _is_migration_applied(conn, "test_flag_mark") is False
        _mark_migration_applied(conn, "test_flag_mark")
        conn.commit()
        assert _is_migration_applied(conn, "test_flag_mark") is True
