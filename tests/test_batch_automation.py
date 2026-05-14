"""批量自动化创作：规划校验等单元测试"""

import json

import pytest
from starlette.datastructures import UploadFile

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
