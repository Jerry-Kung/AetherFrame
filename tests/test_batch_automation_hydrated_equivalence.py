"""P1-1 等价性校验：list_items_hydrated 批量装配 vs 单条装配。"""

import json

from app.models.creation import CreationPromptPrecreationTask, CreationQuickCreateTask
from app.models.creation_batch import CreationBatchRun, CreationBatchRunItem
from app.models.material import MaterialCharacter
from app.services.creation_service.batch_automation_service import BatchAutomationService
from app.services.creation_service.prompt_precreation_service import (
    PromptPrecreationService,
)
from app.services.creation_service.quick_create_service import QuickCreateService


def _make_char(db, cid: str, name: str) -> MaterialCharacter:
    c = MaterialCharacter(
        id=cid,
        name=name,
        display_name=name,
        status="done",
        setting_text="",
        official_photos_json="[null,null,null,null,null]",
        bio_json="{}",
    )
    db.add(c)
    db.commit()
    return c


def _make_ppc(db, tid: str, character_id: str) -> CreationPromptPrecreationTask:
    cards = [
        {"id": f"{tid}-card1", "title": "卡1", "body": "正文1"},
        {"id": f"{tid}-card2", "title": "卡2", "body": "正文2"},
    ]
    t = CreationPromptPrecreationTask(
        id=tid,
        character_id=character_id,
        seed_prompt="seed",
        n=2,
        work_dir=f"/tmp/{tid}",
        status="completed",
        error_message=None,
        result_json=json.dumps(cards, ensure_ascii=False),
        current_step=None,
        chain_quick_create=False,
        chain_qc_n=None,
        chain_qc_aspect_ratio=None,
        chain_qc_max_prompts=None,
        chained_quick_create_task_id=None,
        chain_error=None,
    )
    db.add(t)
    db.commit()
    return t


def _make_qc(db, tid: str, character_id: str) -> CreationQuickCreateTask:
    selected = [{"id": "p1", "title": "T1", "body": "B1"}]
    results = [
        {
            "prompt_id": "p1",
            "generated_images": [{"path": f"{tid}/img1.png", "review": None}],
        }
    ]
    t = CreationQuickCreateTask(
        id=tid,
        character_id=character_id,
        seed_prompt="seed",
        n=1,
        aspect_ratio="1:1",
        selected_prompts_json=json.dumps(selected, ensure_ascii=False),
        status="completed",
        error_message=None,
        result_json=json.dumps(results, ensure_ascii=False),
        work_dir=f"/tmp/{tid}",
        current_step=None,
    )
    db.add(t)
    db.commit()
    return t


def _make_run_with_items(db, run_id: str, items_spec):
    run = CreationBatchRun(
        id=run_id,
        status="completed",
        iterations_total=len(items_spec),
        iterations_done=len(items_spec),
        config_json="{}",
        error_message=None,
    )
    db.add(run)
    db.commit()
    for i, (item_id, char_id, ppc_id, qc_id, status) in enumerate(items_spec):
        item = CreationBatchRunItem(
            id=item_id,
            run_id=run_id,
            step_index=i,
            character_id=char_id,
            seed_prompt_id=f"seed-{i}",
            seed_section="general",
            seed_prompt_text=f"种子-{i}",
            seed_creative_direction_id=None,
            prompt_precreation_task_id=ppc_id,
            quick_create_task_id=qc_id,
            status=status,
            error_message=None,
        )
        db.add(item)
    db.commit()


def _legacy_hydrated(db, limit: int, offset: int):
    """复刻 P1-1 改造前的单条装配逻辑，用于回归对比。"""
    from app.repositories.creation_batch_repository import CreationBatchRepository
    from app.repositories.material_repository import MaterialCharacterRepository

    batch_repo = CreationBatchRepository(db)
    material_repo = MaterialCharacterRepository(db)
    rows = batch_repo.list_all_items(limit=limit, offset=offset)
    total = batch_repo.count_all_items()
    items_payload = []
    from app.services.material_service.material_service import MaterialService

    ms = MaterialService(db)
    ppc_service = PromptPrecreationService(db)
    qc_service = QuickCreateService(db)
    from app.repositories.creation_feedback_repository import (
        CreationImageFeedbackRepository,
    )
    from app.services.creation_service.feedback_service import serialize_feedback_row

    feedback_repo = CreationImageFeedbackRepository(db)
    for it in rows:
        run = batch_repo.get_run(it.run_id)
        if not run:
            continue
        ch = material_repo.get_by_id(it.character_id)
        item_data = {
            "id": it.id,
            "run_id": it.run_id,
            "run_status": run.status,
            "step_index": it.step_index,
            "character_id": it.character_id,
            "chara_name": ch.name if ch else "未知角色",
            "chara_avatar": ms.avatar_url_for_character(ch.id, ch.avatar_filename)
            if ch
            else "",
            "seed_prompt_id": it.seed_prompt_id,
            "seed_section": it.seed_section,
            "seed_prompt_text": it.seed_prompt_text,
            "seed_creative_direction_id": it.seed_creative_direction_id,
            "prompt_precreation_task_id": it.prompt_precreation_task_id,
            "quick_create_task_id": it.quick_create_task_id,
            "status": it.status,
            "error_message": it.error_message,
            "created_at": it.created_at,
            "updated_at": it.updated_at,
            "prompt_cards": None,
            "quick_create_results": None,
            "feedbacks": [],
        }
        if it.status == "completed":
            ppc_id = (it.prompt_precreation_task_id or "").strip()
            qc_id = (it.quick_create_task_id or "").strip()
            if ppc_id:
                d = ppc_service.get_history_detail(ppc_id)
                if d:
                    item_data["prompt_cards"] = d.get("cards", [])
            if qc_id:
                d = qc_service.get_history_detail(qc_id)
                if d:
                    item_data["quick_create_results"] = d.get("results", [])
                    item_data["quick_create_selected_prompts"] = d.get(
                        "selected_prompts", []
                    )
            if qc_id:
                item_data["feedbacks"] = [
                    serialize_feedback_row(f)
                    for f in feedback_repo.list_for_task_ids([qc_id]).get(qc_id, [])
                ]
        items_payload.append(item_data)
    return {"items": items_payload, "total": total}


def test_hydrated_equivalence_with_legacy(db_session):
    """新批量装配版 list_items_hydrated 与旧单条装配版逐字段等价。"""
    db = db_session
    _make_char(db, "char_a", "角色A")
    _make_char(db, "char_b", "角色B")

    _make_ppc(db, "ppcpre_aaa", "char_a")
    _make_ppc(db, "ppcpre_bbb", "char_b")
    _make_qc(db, "qcreate_aaa", "char_a")
    _make_qc(db, "qcreate_bbb", "char_b")

    _make_run_with_items(
        db,
        "bb_run_1",
        [
            ("bb_item_1", "char_a", "ppcpre_aaa", "qcreate_aaa", "completed"),
            ("bb_item_2", "char_b", "ppcpre_bbb", "qcreate_bbb", "completed"),
            ("bb_item_3", "char_a", None, None, "running"),  # 非完成态
        ],
    )

    from app.services.creation_service.feedback_service import ImageFeedbackService

    ImageFeedbackService(db).save_feedback(
        task_id="qcreate_aaa",
        prompt_id="p1",
        image_index=0,
        feedback_text="等价性校验用反馈",
        leg_foot_bad=True,
    )

    svc = BatchAutomationService(db)
    new_payload = svc.list_items_hydrated(limit=50, offset=0)
    legacy_payload = _legacy_hydrated(db, limit=50, offset=0)

    assert new_payload["total"] == legacy_payload["total"]
    assert len(new_payload["items"]) == len(legacy_payload["items"])
    for a, b in zip(new_payload["items"], legacy_payload["items"]):
        assert set(a.keys()) == set(b.keys()), f"键集合不一致: {a.keys()} vs {b.keys()}"
        for k in a:
            assert a[k] == b[k], f"字段 {k} 不一致: {a[k]!r} vs {b[k]!r}"

    item_1 = next(it for it in new_payload["items"] if it["id"] == "bb_item_1")
    assert item_1["feedbacks"] == [
        {
            "prompt_id": "p1",
            "image_index": 0,
            "leg_foot_bad": True,
            "feedback_text": "等价性校验用反馈",
            "selected_tags": [],
        }
    ], f"populated feedbacks 未正确装配: {item_1['feedbacks']!r}"


def test_hydrated_returns_empty_when_no_items(db_session):
    """空库时新版应返回 items=[] total=0。"""
    svc = BatchAutomationService(db_session)
    payload = svc.list_items_hydrated(limit=50, offset=0)
    assert payload == {"items": [], "total": 0}
