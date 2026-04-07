"""
素材加工 — 角色 Service 与文件集成测试（使用临时 DATA_DIR + db_session）
"""
import logging
import os
from io import BytesIO
from unittest.mock import patch

import pytest
from starlette.datastructures import UploadFile

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
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
