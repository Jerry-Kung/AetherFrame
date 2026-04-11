import os
from unittest.mock import patch


def _create_five_standard_refs(character_id: str) -> None:
    from app.services.material_service.material_file_service import (
        get_standard_photo_slot_dir,
    )

    slot_dir = get_standard_photo_slot_dir(character_id)
    os.makedirs(slot_dir, exist_ok=True)
    for shot_type in (
        "full_front",
        "full_side",
        "half_front",
        "half_side",
        "face_close",
    ):
        with open(os.path.join(slot_dir, f"{shot_type}.png"), "wb") as f:
            f.write(b"x" * 3)


class TestStandardReferencePathsForMultimodalPrompt:
    def test_returns_none_when_slot_missing(self, temp_data_dir, db_session):
        from app.services.material_service import material_file_service as mfs

        assert mfs.standard_reference_paths_for_multimodal_prompt("no_such_slots") is None

    def test_under_threshold_returns_all_five_ordered(self, temp_data_dir, db_session):
        from app.services.material_service import material_file_service as mfs

        cid = "mchar_std_ref_small"
        _create_five_standard_refs(cid)
        out = mfs.standard_reference_paths_for_multimodal_prompt(cid)
        assert out is not None
        assert len(out) == 5
        names = [os.path.basename(p) for p in out]
        assert names == [
            "full_front.png",
            "full_side.png",
            "half_front.png",
            "half_side.png",
            "face_close.png",
        ]

    def test_over_threshold_returns_three_key_angles(self, temp_data_dir, db_session):
        from app.services.material_service import material_file_service as mfs

        cid = "mchar_std_ref_large"
        _create_five_standard_refs(cid)
        # 5 * 3 = 15 bytes total; threshold 10 triggers reduction
        with patch.object(mfs, "STANDARD_REF_PROMPT_TOTAL_BYTES_THRESHOLD", 10):
            out = mfs.standard_reference_paths_for_multimodal_prompt(cid)
        assert out is not None
        assert len(out) == 3
        assert [os.path.basename(p) for p in out] == [
            "full_front.png",
            "half_front.png",
            "face_close.png",
        ]
