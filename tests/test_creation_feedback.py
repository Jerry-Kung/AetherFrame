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


QC_RESULTS = [
    {
        "prompt_id": "p1",
        "full_prompt": "最终 Prompt 甲",
        "generated_images": [
            {"filename": "a0.png", "path": "images/a0.png"},
            {"filename": "a1.png", "path": "images/a1.png"},
            {"filename": "a2.png", "path": "images/a2.png"},
        ],
    },
    {
        "prompt_id": "p2",
        "full_prompt": "最终 Prompt 乙",
        "generated_images": [{"filename": "b0.png", "path": "images/b0.png"}],
    },
]


def make_batch_item_for_task(db_session, qc_task):
    from app.repositories.creation_batch_repository import CreationBatchRepository

    repo = CreationBatchRepository(db_session)
    run = repo.create_run(iterations_total=1, config_json="{}", status="completed")
    item = repo.create_item(
        run_id=run.id,
        step_index=0,
        character_id=qc_task.character_id,
        seed_prompt_id="seed-cs-0",
        seed_section="character_specific",
        seed_prompt_text="窗边坐姿，白色过膝袜",
        status="completed",
    )
    return repo.update_item(
        item.id, {"quick_create_task_id": qc_task.id, "status": "completed"}
    )


class TestBuildExport:
    def test_export_with_batch_item(self, db_session):
        task = make_qc_task(db_session, results=QC_RESULTS)
        item = make_batch_item_for_task(db_session, task)
        svc = ImageFeedbackService(db_session)
        svc.save_feedback(task_id=task.id, prompt_id="p1", image_index=0,
                          feedback_text="脚趾夸张", leg_foot_bad=True)
        svc.save_feedback(task_id=task.id, prompt_id="p1", image_index=2,
                          feedback_text="构图很好", leg_foot_bad=False)

        out = svc.build_export()
        assert out["schema"] == "aetherframe_feedback_v1"
        assert out["exported_at"]
        assert len(out["records"]) == 1
        rec = out["records"][0]
        assert rec["batch_item_id"] == item.id
        assert rec["quick_create_task_id"] == task.id
        assert rec["character_id"] == task.character_id
        assert rec["character_name"] == "fb-char"
        assert rec["seed_prompt_id"] == "seed-cs-0"
        assert rec["seed_section"] == "character_specific"
        assert rec["seed_prompt_text"] == "窗边坐姿，白色过膝袜"
        assert rec["created_at"]
        # 只含有已填 feedback 的 p1 组；p2 无 feedback 不导出
        assert len(rec["prompt_groups"]) == 1
        g = rec["prompt_groups"][0]
        assert g["prompt_id"] == "p1"
        assert g["prompt_index"] == 0
        assert g["prompt_title"] == "p1"  # 无预生成卡片时回落 prompt_id
        assert g["full_prompt"] == "最终 Prompt 甲"
        assert g["total_images"] == 3
        assert g["images"] == [
            {"image_index": 0, "image_path": "images/a0.png",
             "leg_foot_bad": True, "feedback_text": "脚趾夸张"},
            {"image_index": 2, "image_path": "images/a2.png",
             "leg_foot_bad": False, "feedback_text": "构图很好"},
        ]

    def test_export_without_batch_item_falls_back_to_task_seed(self, db_session):
        task = make_qc_task(db_session, results=QC_RESULTS, seed_prompt="手动种子")
        svc = ImageFeedbackService(db_session)
        svc.save_feedback(task_id=task.id, prompt_id="p2", image_index=0,
                          feedback_text="ok", leg_foot_bad=False)
        rec = svc.build_export()["records"][0]
        assert rec["batch_item_id"] is None
        assert rec["seed_prompt_id"] is None
        assert rec["seed_section"] is None
        assert rec["seed_prompt_text"] == "手动种子"
        assert rec["prompt_groups"][0]["prompt_index"] == 1

    def test_export_orders_groups_by_prompt_index_not_fill_order(self, db_session):
        # 先填 p2 再填 p1，验证分组顺序来自 result_json 生成序（prompt_index），
        # 而非填写顺序，也不是 prompt_id 的 UUID 字典序。
        task = make_qc_task(db_session, results=QC_RESULTS)
        svc = ImageFeedbackService(db_session)
        svc.save_feedback(task_id=task.id, prompt_id="p2", image_index=0,
                          feedback_text="乙组反馈", leg_foot_bad=False)
        svc.save_feedback(task_id=task.id, prompt_id="p1", image_index=0,
                          feedback_text="甲组反馈", leg_foot_bad=True)

        rec = svc.build_export()["records"][0]
        assert [g["prompt_id"] for g in rec["prompt_groups"]] == ["p1", "p2"]
        assert [g["prompt_index"] for g in rec["prompt_groups"]] == [0, 1]

    def test_export_skips_dangling_rows_and_empty_is_ok(self, db_session):
        svc = ImageFeedbackService(db_session)
        assert svc.build_export()["records"] == []
        # 悬空 feedback（任务已不存在）跳过且不阻断
        CreationImageFeedbackRepository(db_session).upsert(
            quick_create_task_id="qcreate_gone00000000", prompt_id="p1",
            image_index=0, leg_foot_bad=True, feedback_text="悬空",
        )
        task = make_qc_task(db_session, results=QC_RESULTS)
        svc.save_feedback(task_id=task.id, prompt_id="p1", image_index=1,
                          feedback_text="正常", leg_foot_bad=False)
        out = svc.build_export()
        assert [r["quick_create_task_id"] for r in out["records"]] == [task.id]

    def test_export_image_index_out_of_range_keeps_row(self, db_session):
        task = make_qc_task(db_session, results=QC_RESULTS)
        svc = ImageFeedbackService(db_session)
        svc.save_feedback(task_id=task.id, prompt_id="p2", image_index=5,
                          feedback_text="越界索引", leg_foot_bad=False)
        g = svc.build_export()["records"][0]["prompt_groups"][0]
        assert g["images"][0]["image_path"] == ""
        assert g["images"][0]["feedback_text"] == "越界索引"
