"""批量自动化创作：规划校验等单元测试"""

import json
import uuid

import pytest
from starlette.datastructures import UploadFile

from app.repositories.creation_batch_repository import CreationBatchRepository
from app.repositories.creation_repository import CreationQuickCreateRepository
from app.repositories.material_repository import MaterialCharacterRepository
from app.services.creation_service.batch_automation_service import BatchAutomationService
from app.services.material_service.material_service import MaterialService


class TestBatchAutomationPlan:
    def test_plan_raises_when_not_enough_unique_pairs(self, db_session, sample_image):
        ms = MaterialService(db_session)
        ms.clear_fixed_seed_templates()
        char = ms.create_character("BatchPlan")
        ms.update_setting_text(char.id, "角色设定说明")
        sample_image.seek(0)
        ms.upload_raw_images(
            char.id,
            [UploadFile(filename="r.png", file=sample_image)],
            [["立绘"]],
        )
        urls = [f"https://slot{i}.example/s.png" for i in range(5)]
        seeds = {
            "character_specific": [{"id": "s1", "text": "种子甲", "used": False}],
            "general": [{"id": "g1", "text": "种子乙", "used": False}],
        }
        bio = {"chara_profile": "# 小档案\n正文", "official_seed_prompts": seeds}
        ms.repo.update(
            char.id,
            {
                "official_photos_json": json.dumps(urls, ensure_ascii=False),
                "bio_json": json.dumps(bio, ensure_ascii=False),
            },
        )
        ms._after_character_material_changed(char.id)
        assert ms.get_character(char.id).status == "done"

        svc = BatchAutomationService(db_session)
        _, planned = svc.plan_and_validate(iterations=2, character_ids=[char.id])
        assert len(planned) == 2

        with pytest.raises(ValueError, match="可用"):
            svc.plan_and_validate(iterations=3, character_ids=[char.id])

    def test_plan_raises_when_no_done_characters(self, db_session):
        svc = BatchAutomationService(db_session)
        with pytest.raises(ValueError, match="没有资料已完善"):
            svc.plan_and_validate(iterations=2, character_ids=None)

    def test_plan_includes_fixed_seed_section(self, db_session, sample_image):
        ms = MaterialService(db_session)
        ms.clear_fixed_seed_templates()
        ms.create_fixed_seed_template("固定池A")
        ms.create_fixed_seed_template("固定池B")

        char = ms.create_character("BatchFixedPool")
        ms.update_setting_text(char.id, "角色设定说明")
        sample_image.seek(0)
        ms.upload_raw_images(
            char.id,
            [UploadFile(filename="r.png", file=sample_image)],
            [["立绘"]],
        )
        urls = [f"https://slot{i}.example/s.png" for i in range(5)]
        seeds = {"character_specific": [], "general": []}
        bio = {"chara_profile": "# 小档案\n正文", "official_seed_prompts": seeds}
        ms.repo.update(
            char.id,
            {
                "official_photos_json": json.dumps(urls, ensure_ascii=False),
                "bio_json": json.dumps(bio, ensure_ascii=False),
            },
        )
        ms._after_character_material_changed(char.id)
        assert ms.get_character(char.id).status == "done"

        svc = BatchAutomationService(db_session)
        _, planned = svc.plan_and_validate(iterations=2, character_ids=[char.id])
        assert len(planned) == 2
        assert all(p["character_id"] == char.id for p in planned)
        assert all(p.get("seed_section") == "fixed" for p in planned)
        assert {p["seed_prompt_text"] for p in planned} == {"固定池A", "固定池B"}


class TestBatchAutomationDeleteItem:
    @staticmethod
    def _make_item(db_session, **task_ids):
        char = MaterialCharacterRepository(db_session).create(
            {"id": f"mchar_{uuid.uuid4().hex[:12]}", "name": "batch-delete-char"}
        )
        batch_repo = CreationBatchRepository(db_session)
        run = batch_repo.create_run(iterations_total=1, config_json="{}", status="completed")
        item = batch_repo.create_item(
            run_id=run.id,
            step_index=0,
            character_id=char.id,
            seed_prompt_id="s1",
            seed_section="general",
            seed_prompt_text="seed",
            status="completed",
        )
        if task_ids:
            batch_repo.update_item(item.id, task_ids)
        return batch_repo, item

    def test_delete_item_with_dangling_task_refs(self, db_session):
        """子任务已被单独删除（悬空引用）时，产线记录仍必须能删掉。"""
        batch_repo, item = self._make_item(
            db_session,
            quick_create_task_id="qcreate_gone000000",
            prompt_precreation_task_id="ppcpre_gone000000",
        )

        data = BatchAutomationService(db_session).delete_batch_item(item.id)

        assert data == {"deleted_id": item.id}
        assert batch_repo.get_item(item.id) is None

    def test_delete_item_removes_row_even_if_ppc_missing(self, db_session):
        """qc 存在但 ppc 悬空：qc 应被清理，且记录行必须删除（不能半途 404）。"""
        qc_repo = CreationQuickCreateRepository(db_session)
        char = MaterialCharacterRepository(db_session).create(
            {"id": f"mchar_{uuid.uuid4().hex[:12]}", "name": "batch-delete-char2"}
        )
        qc_task = qc_repo.create(
            character_id=char.id,
            seed_prompt="seed",
            n=1,
            aspect_ratio="16:9",
            selected_prompts=[],
        )
        batch_repo = CreationBatchRepository(db_session)
        run = batch_repo.create_run(iterations_total=1, config_json="{}", status="completed")
        item = batch_repo.create_item(
            run_id=run.id,
            step_index=0,
            character_id=char.id,
            seed_prompt_id="s1",
            seed_section="general",
            seed_prompt_text="seed",
            status="completed",
        )
        batch_repo.update_item(
            item.id,
            {
                "quick_create_task_id": qc_task.id,
                "prompt_precreation_task_id": "ppcpre_gone000000",
            },
        )

        data = BatchAutomationService(db_session).delete_batch_item(item.id)

        assert data == {"deleted_id": item.id}
        assert batch_repo.get_item(item.id) is None
        assert qc_repo.get_by_id(qc_task.id) is None


class TestBatchAutomationBatchDelete:
    @staticmethod
    def _make_item(db_session, *, status="completed"):
        char = MaterialCharacterRepository(db_session).create(
            {"id": f"mchar_{uuid.uuid4().hex[:12]}", "name": "batch-bulk-char"}
        )
        batch_repo = CreationBatchRepository(db_session)
        run = batch_repo.create_run(iterations_total=1, config_json="{}", status="completed")
        item = batch_repo.create_item(
            run_id=run.id,
            step_index=0,
            character_id=char.id,
            seed_prompt_id="s1",
            seed_section="general",
            seed_prompt_text="seed",
            status=status,
        )
        return batch_repo, item

    def test_batch_delete_mixed_statuses(self, db_session):
        """completed/failed 删除；running/pending 跳过；不存在的归入 not_found。"""
        batch_repo, done1 = self._make_item(db_session)
        _, done2 = self._make_item(db_session, status="failed")
        _, running = self._make_item(db_session, status="running")
        _, pending = self._make_item(db_session, status="pending")

        data = BatchAutomationService(db_session).batch_delete_items(
            [done1.id, done2.id, running.id, pending.id, "bb_item_missing0000"]
        )

        assert sorted(data["deleted"]) == sorted([done1.id, done2.id])
        assert sorted(data["skipped_running"]) == sorted([running.id, pending.id])
        assert data["not_found"] == ["bb_item_missing0000"]
        assert data["failed"] == []
        assert batch_repo.get_item(done1.id) is None
        assert batch_repo.get_item(done2.id) is None
        assert batch_repo.get_item(running.id) is not None
        assert batch_repo.get_item(pending.id) is not None

    def test_batch_delete_partial_failure_does_not_block_rest(self, db_session, monkeypatch):
        """某条删除抛异常时：该条进 failed，其余条目照常删除。"""
        batch_repo, ok = self._make_item(db_session)
        _, bad = self._make_item(db_session)

        original = BatchAutomationService.delete_batch_item

        def flaky(self, item_id):
            if item_id == bad.id:
                raise RuntimeError("boom")
            return original(self, item_id)

        monkeypatch.setattr(BatchAutomationService, "delete_batch_item", flaky)

        data = BatchAutomationService(db_session).batch_delete_items([ok.id, bad.id])

        assert data["deleted"] == [ok.id]
        assert data["skipped_running"] == []
        assert data["not_found"] == []
        assert [f["id"] for f in data["failed"]] == [bad.id]
        assert batch_repo.get_item(ok.id) is None
        assert batch_repo.get_item(bad.id) is not None
