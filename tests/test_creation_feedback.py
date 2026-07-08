"""生产出图人工 feedback：repository / service / 导出聚合测试"""

import uuid

from app.repositories.creation_feedback_repository import CreationImageFeedbackRepository
from app.repositories.creation_repository import CreationQuickCreateRepository
from app.repositories.material_repository import MaterialCharacterRepository


def make_qc_task(db_session, *, results=None, seed_prompt="生产种子"):
    """建一条 completed 的一键创作任务（可带 result_json），返回 task。"""
    char = MaterialCharacterRepository(db_session).create(
        {"id": f"mchar_{uuid.uuid4().hex[:12]}", "name": "fb-char"}
    )
    repo = CreationQuickCreateRepository(db_session)
    task = repo.create(
        character_id=char.id,
        seed_prompt=seed_prompt,
        n=2,
        aspect_ratio="1:1",
        selected_prompts=[],
        status="completed",
    )
    if results is not None:
        task = repo.update(task.id, {"result_json": results})
    return task


class TestFeedbackRepository:
    def test_upsert_creates_then_updates_single_row(self, db_session):
        task = make_qc_task(db_session)
        repo = CreationImageFeedbackRepository(db_session)
        row = repo.upsert(
            quick_create_task_id=task.id,
            prompt_id="p1",
            image_index=0,
            leg_foot_bad=True,
            feedback_text="脚趾夸张",
        )
        assert row.id
        row2 = repo.upsert(
            quick_create_task_id=task.id,
            prompt_id="p1",
            image_index=0,
            leg_foot_bad=False,
            feedback_text="修正：其实没问题",
        )
        assert row2.id == row.id
        assert repo.list_all() and len(repo.list_all()) == 1
        got = repo.get_for_image(task.id, "p1", 0)
        assert got is not None
        assert got.leg_foot_bad is False
        assert got.feedback_text == "修正：其实没问题"

    def test_delete_for_image(self, db_session):
        task = make_qc_task(db_session)
        repo = CreationImageFeedbackRepository(db_session)
        repo.upsert(
            quick_create_task_id=task.id, prompt_id="p1", image_index=1,
            leg_foot_bad=False, feedback_text="备注",
        )
        assert repo.delete_for_image(task.id, "p1", 1) is True
        assert repo.delete_for_image(task.id, "p1", 1) is False  # 幂等
        assert repo.get_for_image(task.id, "p1", 1) is None

    def test_list_for_task_ids_groups_by_task(self, db_session):
        t1 = make_qc_task(db_session)
        t2 = make_qc_task(db_session)
        repo = CreationImageFeedbackRepository(db_session)
        repo.upsert(quick_create_task_id=t1.id, prompt_id="p1", image_index=0,
                    leg_foot_bad=True, feedback_text="a")
        repo.upsert(quick_create_task_id=t1.id, prompt_id="p2", image_index=1,
                    leg_foot_bad=False, feedback_text="b")
        repo.upsert(quick_create_task_id=t2.id, prompt_id="p1", image_index=0,
                    leg_foot_bad=False, feedback_text="c")
        grouped = repo.list_for_task_ids([t1.id, t2.id, "qcreate_missing"])
        assert set(grouped.keys()) == {t1.id, t2.id}
        assert len(grouped[t1.id]) == 2
        assert len(grouped[t2.id]) == 1
        assert repo.list_for_task_ids([]) == {}

    def test_delete_for_task_removes_all_rows(self, db_session):
        task = make_qc_task(db_session)
        repo = CreationImageFeedbackRepository(db_session)
        for i in range(3):
            repo.upsert(quick_create_task_id=task.id, prompt_id="p1", image_index=i,
                        leg_foot_bad=False, feedback_text=f"n{i}")
        assert repo.delete_for_task(task.id) == 3
        assert repo.list_all() == []


from app.services.creation_service.feedback_service import ImageFeedbackService


class TestImageFeedbackService:
    def test_save_creates_row_and_returns_payload(self, db_session):
        task = make_qc_task(db_session)
        svc = ImageFeedbackService(db_session)
        data = svc.save_feedback(
            task_id=task.id, prompt_id="p1", image_index=0,
            feedback_text="袜口花边过重", leg_foot_bad=True,
        )
        assert data == {
            "prompt_id": "p1",
            "image_index": 0,
            "leg_foot_bad": True,
            "feedback_text": "袜口花边过重",
        }

    def test_save_empty_clears_row(self, db_session):
        task = make_qc_task(db_session)
        svc = ImageFeedbackService(db_session)
        svc.save_feedback(task_id=task.id, prompt_id="p1", image_index=0,
                          feedback_text="临时", leg_foot_bad=False)
        data = svc.save_feedback(task_id=task.id, prompt_id="p1", image_index=0,
                                 feedback_text="   ", leg_foot_bad=False)
        assert data is None
        assert CreationImageFeedbackRepository(db_session).list_all() == []
        # 行本不存在时清空也幂等成功
        assert svc.save_feedback(task_id=task.id, prompt_id="p9", image_index=0,
                                 feedback_text="", leg_foot_bad=False) is None

    def test_save_only_checkbox_is_filled(self, db_session):
        task = make_qc_task(db_session)
        data = ImageFeedbackService(db_session).save_feedback(
            task_id=task.id, prompt_id="p1", image_index=2,
            feedback_text="", leg_foot_bad=True,
        )
        assert data is not None and data["leg_foot_bad"] is True

    def test_save_missing_task_raises(self, db_session):
        import pytest as _pytest
        with _pytest.raises(ValueError, match="任务不存在"):
            ImageFeedbackService(db_session).save_feedback(
                task_id="qcreate_missing0000", prompt_id="p1", image_index=0,
                feedback_text="x", leg_foot_bad=False,
            )

    def test_quick_create_delete_history_removes_feedback(self, db_session):
        from app.services.creation_service.quick_create_service import QuickCreateService

        task = make_qc_task(db_session)
        ImageFeedbackService(db_session).save_feedback(
            task_id=task.id, prompt_id="p1", image_index=0,
            feedback_text="将被联动删除", leg_foot_bad=True,
        )
        QuickCreateService(db_session).delete_history(task.id)
        assert CreationImageFeedbackRepository(db_session).list_all() == []
