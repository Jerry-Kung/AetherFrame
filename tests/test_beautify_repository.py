"""image_beautify_tasks 表与 BeautifyRepository 测试。"""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.beautify import ImageBeautifyTask
from app.repositories.beautify_repository import BeautifyRepository


def _new_task_id() -> str:
    return f"bty_{uuid.uuid4().hex[:12]}"


def _task_payload(**overrides):
    base = {
        "id": _new_task_id(),
        "source_kind": "quick_create",
        "source_task_id": "qcreate_test001",
        "source_image_path": "outputs/img_01.png",
        "status": "pending",
    }
    base.update(overrides)
    return base


@pytest.fixture
def beautify_repo(db_session):
    return BeautifyRepository(db_session)


class TestBeautifyRepositoryCrud:
    def test_create_get_update_delete(self, beautify_repo):
        payload = _task_payload()
        created = beautify_repo.create(payload)
        assert created.id == payload["id"]
        assert created.source_kind == "quick_create"

        fetched = beautify_repo.get_by_id(payload["id"])
        assert fetched is not None
        assert fetched.source_image_path == "outputs/img_01.png"

        updated = beautify_repo.update(
            payload["id"],
            {"status": "processing", "current_step": "uploading"},
        )
        assert updated is not None
        assert updated.status == "processing"
        assert updated.current_step == "uploading"

        assert beautify_repo.delete(payload["id"]) is True
        assert beautify_repo.get_by_id(payload["id"]) is None

    def test_unique_source_constraint(self, beautify_repo):
        payload = _task_payload()
        beautify_repo.create(payload)
        with pytest.raises(IntegrityError):
            beautify_repo.create(
                _task_payload(
                    id=_new_task_id(),
                    source_kind=payload["source_kind"],
                    source_task_id=payload["source_task_id"],
                    source_image_path=payload["source_image_path"],
                )
            )
        beautify_repo.db.rollback()


class TestBeautifyRepositoryQueries:
    def test_get_inflight(self, beautify_repo):
        payload = _task_payload(status="processing", current_step="polling")
        beautify_repo.create(payload)

        inflight = beautify_repo.get_inflight(
            "quick_create", "qcreate_test001", "outputs/img_01.png"
        )
        assert inflight is not None
        assert inflight.id == payload["id"]

        beautify_repo.update(payload["id"], {"status": "completed"})
        assert (
            beautify_repo.get_inflight(
                "quick_create", "qcreate_test001", "outputs/img_01.png"
            )
            is None
        )

    def test_get_by_source(self, beautify_repo):
        payload = _task_payload(source_kind="repair", source_task_id="repair_abc")
        beautify_repo.create(payload)

        row = beautify_repo.get_by_source(
            "repair", "repair_abc", "outputs/img_01.png"
        )
        assert row is not None
        assert row.source_kind == "repair"

    def test_list_by_source(self, beautify_repo):
        tid = "qcreate_multi"
        beautify_repo.create(
            _task_payload(
                source_task_id=tid,
                source_image_path="a.png",
            )
        )
        beautify_repo.create(
            _task_payload(
                source_task_id=tid,
                source_image_path="b.png",
            )
        )
        beautify_repo.create(
            _task_payload(
                source_task_id="other",
                source_image_path="c.png",
            )
        )

        rows = beautify_repo.list_by_source("quick_create", tid)
        assert len(rows) == 2
        paths = {r.source_image_path for r in rows}
        assert paths == {"a.png", "b.png"}

    def test_list_by_external_id(self, beautify_repo):
        ext_id = "bigjpg-ext-12345"
        p1 = _task_payload(
            source_image_path="x1.png",
            external_task_id=ext_id,
        )
        p2 = _task_payload(
            source_image_path="x2.png",
            external_task_id=ext_id,
        )
        beautify_repo.create(p1)
        beautify_repo.create(p2)

        rows = beautify_repo.list_by_external_id(ext_id)
        assert len(rows) == 2
        assert {r.id for r in rows} == {p1["id"], p2["id"]}


class TestBeautifyTableSchema:
    def test_table_registered_after_init_db(self, temp_data_dir):
        import sys

        for key in list(sys.modules.keys()):
            if key.startswith("app.models") or key.startswith("app.repositories"):
                del sys.modules[key]

        from app.models import database

        database.init_db()
        assert "image_beautify_tasks" in database.Base.metadata.tables

        from sqlalchemy import inspect

        insp = inspect(database.engine)
        assert "image_beautify_tasks" in insp.get_table_names()
        indexes = {idx["name"] for idx in insp.get_indexes("image_beautify_tasks")}
        assert "ix_beautify_status_created" in indexes

        unique_cols = {
            tuple(uc["column_names"])
            for uc in insp.get_unique_constraints("image_beautify_tasks")
        }
        assert ("source_kind", "source_task_id", "source_image_path") in unique_cols
