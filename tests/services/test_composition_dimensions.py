import pytest

from app.services.creation_service.composition_dimensions import (
    DimensionValue,
    VALID_AUTO_ASPECT_CODES,
    VALID_MANUAL_ASPECT_CODES,
    get_dimension_values,
    get_home_setting_pose_hints,
)


def test_manual_aspect_ratio_returns_five_values():
    values = get_dimension_values("aspect_ratio_manual")
    assert len(values) == 5
    codes = {v.code for v in values}
    assert codes == {"16:9", "4:3", "1:1", "3:4", "9:16"}
    assert VALID_MANUAL_ASPECT_CODES == frozenset(codes)


def test_auto_aspect_ratio_full_has_nine_values_and_includes_manual_five():
    values = get_dimension_values("aspect_ratio_auto_full")
    codes = {v.code for v in values}
    assert len(codes) == 9
    assert VALID_MANUAL_ASPECT_CODES.issubset(codes)
    assert VALID_AUTO_ASPECT_CODES == frozenset(codes)
    for extra in ("4:5", "5:4", "2:3", "3:2"):
        assert extra in codes


def test_auto_aspect_ratio_mainstream_is_the_five_manual():
    values = get_dimension_values("aspect_ratio_auto_mainstream")
    assert {v.code for v in values} == VALID_MANUAL_ASPECT_CODES


def test_subject_area_min_four_tiers():
    values = get_dimension_values("subject_area_min")
    codes = [v.code for v in values]
    assert codes == ["0.45", "0.55", "0.65", "0.75"]


def test_pose_family_six_tiers():
    values = get_dimension_values("pose_family")
    display = {v.display_name for v in values}
    assert display == {"坐姿", "躺姿", "跪姿", "蹲姿", "倚靠", "盘腿坐"}


def test_shooting_angle_five_tiers_includes_back_glance():
    values = get_dimension_values("shooting_angle")
    codes = {v.code for v in values}
    assert "back_glance" in codes
    assert len(codes) == 5


def test_camera_height_four_tiers():
    values = get_dimension_values("camera_height")
    codes = {v.code for v in values}
    assert codes == {"slight_up", "eye_level", "slight_down", "high_down"}


def test_gaze_direction_five_tiers():
    values = get_dimension_values("gaze_direction")
    assert len({v.code for v in values}) == 5


def test_unknown_dimension_raises():
    with pytest.raises(KeyError):
        get_dimension_values("no_such_dimension")


def test_dimension_value_has_all_three_fields():
    v = get_dimension_values("pose_family")[0]
    assert isinstance(v, DimensionValue)
    assert v.code and v.display_name and v.description


def test_home_setting_pose_hints_returns_tuples_with_nonempty_lists():
    hints = get_home_setting_pose_hints()
    assert len(hints) >= 5
    for setting, poses in hints:
        assert isinstance(setting, str) and setting
        assert isinstance(poses, list) and all(isinstance(p, str) and p for p in poses)
