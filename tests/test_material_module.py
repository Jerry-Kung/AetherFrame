"""
素材加工 — 角色 Service 与文件集成测试（使用临时 DATA_DIR + db_session）
"""
import json
import logging
import os
from io import BytesIO
from unittest.mock import patch

import pytest
from starlette.datastructures import UploadFile

from app.datetime_display import configure_logging

configure_logging(logging.DEBUG)
logger = logging.getLogger(__name__)


def _png_bytes():
    return bytes(
        [
            0x89,
            0x50,
            0x4E,
            0x47,
            0x0D,
            0x0A,
            0x1A,
            0x0A,
            0x00,
            0x00,
            0x00,
            0x0D,
            0x49,
            0x48,
            0x44,
            0x52,
            0x00,
            0x00,
            0x00,
            0x01,
            0x00,
            0x00,
            0x00,
            0x01,
            0x08,
            0x02,
            0x00,
            0x00,
            0x00,
            0x90,
            0x77,
            0x53,
            0xDE,
            0x00,
            0x00,
            0x00,
            0x0C,
            0x49,
            0x44,
            0x41,
            0x54,
            0x08,
            0xD7,
            0x63,
            0xF8,
            0xFF,
            0xFF,
            0x3F,
            0x00,
            0x05,
            0xFE,
            0x02,
            0xFE,
            0xA3,
            0x60,
            0x50,
            0xE9,
            0x00,
            0x00,
            0x00,
            0x00,
            0x49,
            0x45,
            0x4E,
            0x44,
            0xAE,
            0x42,
            0x60,
            0x82,
        ]
    )


@pytest.fixture(scope="function")
def material_svc(db_session):
    from app.models.database import init_db
    from app.services import directory_service
    from app.services.material_service import MaterialService

    directory_service.initialize_data_directory()
    init_db()
    return MaterialService(db_session)


@pytest.fixture(scope="function")
def sample_png():
    return _png_bytes()


class TestMaterialCharacterService:
    def test_create_delete_and_dirs(self, material_svc):
        char = material_svc.create_character("测试角色", display_name="展示名")
        assert char.name == "测试角色"
        assert char.display_name == "展示名"
        assert char.status == "idle"

        from app.services.material_service import material_file_service

        char_dir = material_file_service.get_character_dir(char.id)
        assert os.path.isdir(char_dir)

        assert material_svc.delete_character(char.id) is True
        assert material_svc.get_character(char.id) is None
        assert not os.path.isdir(char_dir)

    def test_setting_promotes_draft(self, material_svc):
        char = material_svc.create_character("A")
        char = material_svc.update_setting_text(char.id, "  设定  ")
        assert char.setting_text == "  设定  "
        assert char.status == "draft"

    def test_setting_from_upload_utf8(self, material_svc):
        char = material_svc.create_character("B")
        raw = "# hello\n中文".encode("utf-8")
        up = UploadFile(filename="note.md", file=BytesIO(raw))
        char = material_svc.update_setting_from_upload(char.id, up)
        assert char.setting_text == "# hello\n中文"
        assert char.setting_source_filename == "note.md"

    def test_setting_text_preserves_source_filename_by_default(self, material_svc):
        char = material_svc.create_character("SrcKeep")
        raw = b"alpha"
        char = material_svc.update_setting_from_upload(
            char.id, UploadFile(filename="a.txt", file=BytesIO(raw))
        )
        assert char.setting_source_filename == "a.txt"
        char = material_svc.update_setting_text(char.id, "beta")
        assert char.setting_text == "beta"
        assert char.setting_source_filename == "a.txt"

    def test_setting_text_clear_setting_source(self, material_svc):
        char = material_svc.create_character("SrcClear")
        raw = b"x"
        char = material_svc.update_setting_from_upload(
            char.id, UploadFile(filename="f.md", file=BytesIO(raw))
        )
        assert char.setting_source_filename == "f.md"
        char = material_svc.update_setting_text(char.id, "y", clear_setting_source=True)
        assert char.setting_text == "y"
        assert char.setting_source_filename is None

    def test_upload_raw_images_and_path(self, material_svc, sample_png):
        char = material_svc.create_character("C")
        files = [
            UploadFile(filename="a.png", file=BytesIO(sample_png)),
            UploadFile(filename="b.png", file=BytesIO(sample_png)),
        ]
        tags = [["立绘"], ["其他"]]
        uploaded, failed = material_svc.upload_raw_images(char.id, files, tags)
        assert len(failed) == 0
        assert len(uploaded) == 2
        assert uploaded[0]["tags"] == ["立绘"]
        path = material_svc.get_raw_image_path(char.id, uploaded[0]["filename"])
        assert path and os.path.isfile(path)
        with open(path, "rb") as f:
            assert f.read().startswith(b"\x89PNG")

        char = material_svc.get_character(char.id)
        assert char.status == "draft"
        detail = material_svc.character_to_detail_dict(char)
        assert len(detail["raw_images"]) == 2

    def test_list_summaries(self, material_svc, sample_png):
        material_svc.create_character("X")
        items, total = material_svc.list_character_summaries()
        assert total >= 1
        assert any(x["name"] == "X" for x in items)

    def test_list_summaries_avatar_url_from_first_raw(self, material_svc, sample_png):
        char = material_svc.create_character("Av")
        material_svc.upload_raw_images(
            char.id,
            [UploadFile(filename="a.png", file=BytesIO(sample_png))],
            [["立绘"]],
        )
        items, _ = material_svc.list_character_summaries()
        row = next(x for x in items if x["id"] == char.id)
        assert row["avatar_url"].startswith(f"/api/material/characters/{char.id}/images/raw/")

    def test_patch_character(self, material_svc):
        char = material_svc.create_character("Old", display_name="OldDisp")
        char = material_svc.patch_character(char.id, name="New", display_name="NewDisp")
        assert char.name == "New"
        assert char.display_name == "NewDisp"

    def test_upload_character_avatar_sets_file_and_detail_url(self, material_svc, sample_png):
        char = material_svc.create_character("AvatarChar")
        up = UploadFile(filename="avatar.png", file=BytesIO(sample_png))
        char2 = material_svc.upload_character_avatar(char.id, up)
        assert char2.avatar_filename == "avatar.png"
        detail = material_svc.character_to_detail_dict(material_svc.get_character(char.id))
        assert detail["avatar_url"] == (
            f"/api/material/characters/{char.id}/images/avatar/{char2.avatar_filename}"
        )
        assert detail["raw_images"] == []
        path = material_svc.get_avatar_image_path(char.id, char2.avatar_filename)
        assert path and os.path.isfile(path)

    def test_upload_character_avatar_list_summary_prefers_avatar_slot(self, material_svc, sample_png):
        char = material_svc.create_character("AvSlot")
        material_svc.upload_raw_images(
            char.id,
            [UploadFile(filename="older.png", file=BytesIO(sample_png))],
            [["立绘"]],
        )
        material_svc.upload_character_avatar(
            char.id,
            UploadFile(filename="face.png", file=BytesIO(sample_png)),
        )
        char3 = material_svc.get_character(char.id)
        items, _ = material_svc.list_character_summaries()
        row = next(x for x in items if x["id"] == char.id)
        assert char3.avatar_filename in row["avatar_url"]
        assert row["avatar_url"] == (
            f"/api/material/characters/{char.id}/images/avatar/{char3.avatar_filename}"
        )

    def test_upload_character_avatar_unknown_character_raises(self, material_svc, sample_png):
        up = UploadFile(filename="a.png", file=BytesIO(sample_png))
        with pytest.raises(ValueError, match="角色不存在"):
            material_svc.upload_character_avatar("mchar_nonexistent_xx", up)

    def test_material_complete_sets_done_status(self, material_svc, sample_png):
        char = material_svc.create_character("Complete")
        material_svc.update_setting_text(char.id, "角色设定说明内容")
        material_svc.upload_raw_images(
            char.id,
            [UploadFile(filename="r.png", file=BytesIO(sample_png))],
            [["立绘"]],
        )
        urls = [f"https://slot{i}.example/s.png" for i in range(5)]
        bio = json.dumps({"chara_profile": "# 小档案\n正文已生成"}, ensure_ascii=False)
        material_svc.repo.update(
            char.id,
            {
                "official_photos_json": json.dumps(urls, ensure_ascii=False),
                "bio_json": bio,
            },
        )
        material_svc._after_character_material_changed(char.id)
        assert material_svc.get_character(char.id).status == "done"

    def test_material_done_demotes_when_standard_slot_cleared(self, material_svc, sample_png):
        char = material_svc.create_character("Demote")
        material_svc.update_setting_text(char.id, "设定")
        material_svc.upload_raw_images(
            char.id,
            [UploadFile(filename="r.png", file=BytesIO(sample_png))],
            None,
        )
        urls = [f"https://x{i}.test/p.png" for i in range(5)]
        bio = json.dumps({"chara_profile": "档案"}, ensure_ascii=False)
        material_svc.repo.update(
            char.id,
            {"official_photos_json": json.dumps(urls, ensure_ascii=False), "bio_json": bio},
        )
        material_svc._after_character_material_changed(char.id)
        assert material_svc.get_character(char.id).status == "done"
        material_svc.clear_official_photo_slot(char.id, 0)
        assert material_svc.get_character(char.id).status == "draft"

    def test_delete_raw_image_removes_file(self, material_svc, sample_png):
        char = material_svc.create_character("D")
        uploaded, _ = material_svc.upload_raw_images(
            char.id,
            [UploadFile(filename="a.png", file=BytesIO(sample_png))],
            None,
        )
        iid = uploaded[0]["id"]
        fn = uploaded[0]["filename"]
        path = material_svc.get_raw_image_path(char.id, fn)
        assert path and os.path.isfile(path)
        assert material_svc.delete_raw_image(char.id, iid) is True
        assert not os.path.isfile(path)
        detail = material_svc.character_to_detail_dict(material_svc.get_character(char.id))
        assert len(detail["raw_images"]) == 0

    def test_update_raw_image_tags(self, material_svc, sample_png):
        char = material_svc.create_character("T")
        uploaded, _ = material_svc.upload_raw_images(
            char.id,
            [UploadFile(filename="a.png", file=BytesIO(sample_png))],
            [["其他"]],
        )
        iid = uploaded[0]["id"]
        assert material_svc.update_raw_image_tags(char.id, iid, ["表情", "立绘"]) is True
        detail = material_svc.character_to_detail_dict(material_svc.get_character(char.id))
        assert detail["raw_images"][0]["tags"] == ["表情", "立绘"]

    def test_character_detail_official_photos_compat_to_five_slots(self, material_svc):
        char = material_svc.create_character("Compat")
        material_svc.repo.update(char.id, {"official_photos_json": "[\"a\",\"b\",\"c\"]"})
        detail = material_svc.character_to_detail_dict(material_svc.get_character(char.id))
        assert len(detail["official_photos"]) == 5
        assert detail["official_photos"][:3] == ["a", "b", "c"]
        assert detail["official_photos"][3] is None
        assert detail["official_photos"][4] is None

    def test_standard_photo_task_start_and_select(self, material_svc, sample_png):
        char = material_svc.create_character("Std")
        files = [
            UploadFile(filename="official.png", file=BytesIO(sample_png)),
            UploadFile(filename="fanart.png", file=BytesIO(sample_png)),
        ]
        uploaded, _ = material_svc.upload_raw_images(
            char.id, files, [["立绘"], ["立绘"]], ["official", "fanart"]
        )
        selected_ids = [x["id"] for x in uploaded]

        with patch(
            "app.services.material_service.standard_photo_generation_service.generate_standard_photo_images",
            return_value=([], None, None),
        ):
            material_svc.start_standard_photo_task(
                character_id=char.id,
                shot_type="full_front",
                aspect_ratio="1:1",
                output_count=2,
                selected_raw_image_ids=selected_ids,
                background_tasks=None,
            )
        status = material_svc.get_standard_photo_task_status(char.id)
        assert status is not None
        assert status["status"] == "failed"

    def test_standard_photo_execute_and_save(self, material_svc, sample_png):
        char = material_svc.create_character("Std2")
        uploaded, _ = material_svc.upload_raw_images(
            char.id,
            [UploadFile(filename="official.png", file=BytesIO(sample_png))],
            [["立绘"]],
            ["official"],
        )
        selected_ids = [uploaded[0]["id"]]

        temp_dir = os.path.join(os.getenv("DATA_DIR", "./data"), "tmp_test_std")
        os.makedirs(temp_dir, exist_ok=True)
        temp_file = os.path.join(temp_dir, "mock.png")
        with open(temp_file, "wb") as f:
            f.write(sample_png)

        with patch(
            "app.services.material_service.standard_photo_generation_service.generate_standard_photo_images",
            return_value=([temp_file], None, temp_dir),
        ):
            material_svc.start_standard_photo_task(
                character_id=char.id,
                shot_type="face_close",
                aspect_ratio="9:16",
                output_count=1,
                selected_raw_image_ids=selected_ids,
                background_tasks=None,
            )

        status = material_svc.get_standard_photo_task_status(char.id)
        assert status is not None
        assert status["status"] == "completed"
        assert len(status["result_images"]) == 1
        result_url = status["result_images"][0]
        result_filename = result_url.rstrip("/").rsplit("/", 1)[-1].split("?")[0]

        updated_char = material_svc.select_standard_photo_result(
            char.id,
            selected_result_filename=result_filename,
            selected_result_index=None,
        )
        detail = material_svc.character_to_detail_dict(updated_char)
        assert len(detail["official_photos"]) == 5
        assert detail["official_photos"][4] is not None
        assert "slot-images" in (detail["official_photos"][4] or "")
        assert "face_close" in (detail["official_photos"][4] or "")

    def test_clear_official_photo_slot_clears_json_and_removes_file(self, material_svc, sample_png):
        char = material_svc.create_character("StdDel")
        uploaded, _ = material_svc.upload_raw_images(
            char.id,
            [UploadFile(filename="official.png", file=BytesIO(sample_png))],
            [["立绘"]],
            ["official"],
        )
        selected_ids = [uploaded[0]["id"]]

        temp_dir = os.path.join(os.getenv("DATA_DIR", "./data"), "tmp_test_std_del")
        os.makedirs(temp_dir, exist_ok=True)
        temp_file = os.path.join(temp_dir, "mock.png")
        with open(temp_file, "wb") as f:
            f.write(sample_png)

        with patch(
            "app.services.material_service.standard_photo_generation_service.generate_standard_photo_images",
            return_value=([temp_file], None, temp_dir),
        ):
            material_svc.start_standard_photo_task(
                character_id=char.id,
                shot_type="full_front",
                aspect_ratio="1:1",
                output_count=1,
                selected_raw_image_ids=selected_ids,
                background_tasks=None,
            )

        from app.services.material_service import material_file_service

        assert material_svc.get_standard_photo_task_status(char.id)["status"] == "completed"
        st = material_svc.get_standard_photo_task_status(char.id)
        result_filename = st["result_images"][0].rstrip("/").rsplit("/", 1)[-1].split("?")[0]
        material_svc.select_standard_photo_result(
            char.id,
            selected_result_filename=result_filename,
            selected_result_index=None,
        )
        slot_path = material_file_service.get_standard_slot_image_path(char.id, "full_front")
        assert slot_path and os.path.isfile(slot_path)

        cleared = material_svc.clear_official_photo_slot(char.id, 0)
        detail = material_svc.character_to_detail_dict(cleared)
        assert detail["official_photos"][0] is None
        assert not os.path.isfile(slot_path)

    def test_clear_official_photo_slot_idempotent_on_empty_slot(self, material_svc):
        char = material_svc.create_character("StdIdem")
        d1 = material_svc.character_to_detail_dict(material_svc.clear_official_photo_slot(char.id, 2))
        d2 = material_svc.character_to_detail_dict(material_svc.clear_official_photo_slot(char.id, 2))
        assert d1["official_photos"][2] is None
        assert d2["official_photos"][2] is None

    def test_clear_official_photo_slot_unknown_character_raises(self, material_svc):
        with pytest.raises(ValueError, match="角色不存在"):
            material_svc.clear_official_photo_slot("mchar_nonexistent_zz", 0)

    def test_clear_official_photo_slot_invalid_index_raises(self, material_svc):
        char = material_svc.create_character("StdBadIdx")
        with pytest.raises(ValueError, match="标准照槽位索引无效"):
            material_svc.clear_official_photo_slot(char.id, 5)

    def test_chara_profile_task_pipeline_and_artifacts(self, material_svc, sample_png):
        from app.repositories.material_repository import INDEX_TO_SHOT_TYPE
        from app.services.material_service import material_file_service

        char = material_svc.create_character("Prof")
        material_svc.update_setting_text(char.id, "人设说明内容")
        slot_dir = material_file_service.get_standard_photo_slot_dir(char.id)
        os.makedirs(slot_dir, exist_ok=True)
        for i in range(5):
            st = INDEX_TO_SHOT_TYPE[i]
            with open(os.path.join(slot_dir, f"{st}.png"), "wb") as f:
                f.write(sample_png)
        uploaded, _ = material_svc.upload_raw_images(
            char.id,
            [UploadFile(filename="fanart.png", file=BytesIO(sample_png))],
            [["立绘"]],
            ["fanart"],
        )
        fan_id = uploaded[0]["id"]

        def fake_infer(*_a, **_kw):
            return "## mock result\n"

        with patch(
            "app.services.material_service.chara_profile_generation_service.yibu_gemini_infer",
            side_effect=fake_infer,
        ):
            material_svc.start_chara_profile_task(
                character_id=char.id,
                selected_fanart_ids=[fan_id],
                background_tasks=None,
            )

        st = material_svc.get_chara_profile_task_status(char.id)
        assert st["status"] == "completed"
        assert st["current_step"] == "done"
        cp_dir = material_file_service.get_chara_profile_dir(char.id)
        for name in material_file_service.CHARA_PROFILE_ARTIFACT_NAMES:
            assert os.path.isfile(os.path.join(cp_dir, name))
        char2 = material_svc.get_character(char.id)
        bio = json.loads(char2.bio_json)
        assert "## mock" in bio["chara_profile"]

    def test_chara_profile_start_requires_standard_slots(self, material_svc, sample_png):
        char = material_svc.create_character("Prof2")
        material_svc.update_setting_text(char.id, "人设")
        uploaded, _ = material_svc.upload_raw_images(
            char.id,
            [UploadFile(filename="fanart.png", file=BytesIO(sample_png))],
            [["立绘"]],
            ["fanart"],
        )
        with pytest.raises(ValueError, match="标准参考照"):
            material_svc.start_chara_profile_task(
                character_id=char.id,
                selected_fanart_ids=[uploaded[0]["id"]],
                background_tasks=None,
            )

    def test_patch_character_bio_merge(self, material_svc):
        char = material_svc.create_character("BioMerge")
        material_svc.repo.update(
            char.id,
            {"bio_json": '{"chara_profile": "profile_keep", "other": 1}'},
        )
        material_svc.patch_character_bio(char.id, creative_advice="advice_only")
        char2 = material_svc.get_character(char.id)
        bio = json.loads(char2.bio_json)
        assert bio["chara_profile"] == "profile_keep"
        assert bio["creative_advice"] == "advice_only"
        assert bio["other"] == 1

    def test_patch_character_bio_official_seed_prompts(self, material_svc):
        char = material_svc.create_character("SeedBio")
        material_svc.repo.update(
            char.id,
            {"bio_json": '{"chara_profile": "p", "creative_advice": "a"}'},
        )
        payload = {
            "character_specific": [{"id": "1", "text": "专属", "used": False}],
            "general": [{"id": "2", "text": "通用", "used": True}],
        }
        material_svc.patch_character_bio(char.id, official_seed_prompts=payload)
        char2 = material_svc.get_character(char.id)
        bio = json.loads(char2.bio_json)
        assert bio["chara_profile"] == "p"
        assert bio["creative_advice"] == "a"
        assert bio["official_seed_prompts"] == payload

    def test_patch_character_bio_official_seed_prompts_clear_removes_key(self, material_svc):
        char = material_svc.create_character("SeedClear")
        material_svc.repo.update(
            char.id,
            {
                "bio_json": json.dumps(
                    {
                        "chara_profile": "p",
                        "official_seed_prompts": {
                            "character_specific": [{"id": "1", "text": "a", "used": False}],
                            "general": [{"id": "2", "text": "b", "used": True}],
                        },
                    },
                    ensure_ascii=False,
                )
            },
        )
        material_svc.patch_character_bio(
            char.id,
            official_seed_prompts={"character_specific": [], "general": []},
        )
        char2 = material_svc.get_character(char.id)
        bio = json.loads(char2.bio_json)
        assert bio["chara_profile"] == "p"
        assert "official_seed_prompts" not in bio

    def test_patch_character_bio_official_seed_prompts_delete_one_row(self, material_svc):
        char = material_svc.create_character("SeedDel")
        material_svc.repo.update(
            char.id,
            {
                "bio_json": json.dumps(
                    {
                        "official_seed_prompts": {
                            "character_specific": [
                                {"id": "1", "text": "keep", "used": False},
                                {"id": "2", "text": "gone", "used": True},
                            ],
                            "general": [{"id": "g1", "text": "gen", "used": False}],
                        }
                    },
                    ensure_ascii=False,
                )
            },
        )
        payload = {
            "character_specific": [{"id": "1", "text": "keep", "used": False}],
            "general": [{"id": "g1", "text": "gen", "used": False}],
        }
        material_svc.patch_character_bio(char.id, official_seed_prompts=payload)
        bio = json.loads(material_svc.get_character(char.id).bio_json)
        assert bio["official_seed_prompts"] == payload

    def test_start_creation_advice_missing_prerequisite(self, material_svc):
        char = material_svc.create_character("CADV0")
        with pytest.raises(ValueError, match="text_understanding"):
            material_svc.start_creation_advice_task(char.id, background_tasks=None)

    def test_creation_advice_task_success(self, material_svc):
        from app.services.material_service import material_file_service

        char = material_svc.create_character("CADV1")
        cp_dir = material_file_service.get_chara_profile_dir(char.id)
        os.makedirs(cp_dir, exist_ok=True)
        for name in material_file_service.CHARA_PROFILE_ARTIFACT_NAMES:
            with open(os.path.join(cp_dir, name), "w", encoding="utf-8") as f:
                f.write("body\n")

        calls = []

        def fake_infer(prompt: str, **_kw):
            calls.append(prompt)
            if "请以JSON格式给出你的输出" in prompt:
                return '{"character_specific": ["种子A"], "general": ["通用B"]}'
            return "# 创作建议\n\n段落"

        with patch(
            "app.services.material_service.creation_advice_generation_service.yibu_gemini_infer",
            side_effect=fake_infer,
        ):
            material_svc.start_creation_advice_task(char.id, background_tasks=None)

        st = material_svc.get_creation_advice_task_status(char.id)
        assert st["status"] == "completed"
        assert st["current_step"] == "done"
        assert st["seed_draft"] == {"character_specific": ["种子A"], "general": ["通用B"]}
        adv_path = os.path.join(cp_dir, material_file_service.CREATION_ADVICE_MD_FILENAME)
        assert os.path.isfile(adv_path)
        char2 = material_svc.get_character(char.id)
        bio = json.loads(char2.bio_json)
        assert bio["creative_advice"] == "# 创作建议\n\n段落"
        assert len(calls) == 2

    def test_creation_advice_history_seeds_in_second_prompt(self, material_svc):
        from app.services.material_service import material_file_service

        char = material_svc.create_character("CADV2")
        material_svc.repo.update(
            char.id,
            {
                "bio_json": json.dumps(
                    {
                        "official_seed_prompts": {
                            "character_specific": [{"id": "1", "text": "历史专属一句", "used": False}],
                            "general": [],
                        }
                    },
                    ensure_ascii=False,
                )
            },
        )
        cp_dir = material_file_service.get_chara_profile_dir(char.id)
        os.makedirs(cp_dir, exist_ok=True)
        for name in material_file_service.CHARA_PROFILE_ARTIFACT_NAMES:
            with open(os.path.join(cp_dir, name), "w", encoding="utf-8") as f:
                f.write("x\n")

        calls = []

        def capture(prompt: str, **_kw):
            calls.append(prompt)
            if "请以JSON格式给出你的输出" in prompt:
                return '{"character_specific": [], "general": []}'
            return "adv"

        with patch(
            "app.services.material_service.creation_advice_generation_service.yibu_gemini_infer",
            side_effect=capture,
        ):
            material_svc.start_creation_advice_task(char.id, background_tasks=None)

        assert len(calls) == 2
        assert "历史专属一句" in calls[1]

    def test_parse_seed_prompt_llm_json_strips_fence(self):
        from app.services.material_service.creation_advice_generation_service import (
            parse_seed_prompt_llm_json,
        )

        raw = '```json\n{"character_specific": ["a"], "general": ["b"]}\n```'
        d = parse_seed_prompt_llm_json(raw)
        assert d == {"character_specific": ["a"], "general": ["b"]}

    def test_build_history_seed_prompts_empty_and_filled(self):
        from app.services.material_service.history_seed_prompts import build_history_seed_prompts

        assert build_history_seed_prompts({}) == "（暂无历史正式种子提示词）"
        bio = {
            "official_seed_prompts": {
                "character_specific": [{"id": "1", "text": "  甲  ", "used": False}],
                "general": [{"id": "2", "text": "乙", "used": True}],
            }
        }
        assert "- 甲" in build_history_seed_prompts(bio)
        assert "- 乙" in build_history_seed_prompts(bio)

        merged = build_history_seed_prompts(bio, fixed_unused_texts=["  固  "])
        assert "- 甲" in merged
        assert "- [固定模板] 固" in merged

        fixed_only = build_history_seed_prompts({}, fixed_unused_texts=["仅固定"])
        assert fixed_only == "- [固定模板] 仅固定"


class TestFixedSeedTemplates:
    def test_crud_and_clear(self, material_svc):
        material_svc.clear_fixed_seed_templates()
        row = material_svc.create_fixed_seed_template("  首条  ")
        assert row["text"] == "首条"
        assert row["used"] is False
        tid = row["id"]
        patched = material_svc.patch_fixed_seed_template(tid, text="已改", used=True)
        assert patched["text"] == "已改"
        assert patched["used"] is True
        listed = material_svc.list_fixed_seed_templates()
        assert any(r["id"] == tid for r in listed)
        material_svc.delete_fixed_seed_template(tid)
        with pytest.raises(ValueError, match="不存在"):
            material_svc.delete_fixed_seed_template(tid)
        material_svc.create_fixed_seed_template("a")
        material_svc.create_fixed_seed_template("b")
        n = material_svc.clear_fixed_seed_templates()
        assert n >= 2
        assert material_svc.list_fixed_seed_templates() == []
