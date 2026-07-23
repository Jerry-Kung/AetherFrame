import pytest

from app.tools.llm.seedance import pick_closest_ratio, SUPPORTED_RATIOS


def test_supported_ratios_nonempty():
    assert "3:4" in SUPPORTED_RATIOS
    assert "16:9" in SUPPORTED_RATIOS


@pytest.mark.parametrize(
    "w,h,expected",
    [
        (1080, 1440, "3:4"),   # 竖图
        (1920, 1080, "16:9"),  # 横图
        (1000, 1000, "1:1"),   # 方图
        (1080, 1920, "9:16"),  # 长竖
    ],
)
def test_pick_closest_ratio(w, h, expected):
    assert pick_closest_ratio(w, h) == expected


def test_pick_closest_ratio_zero_height_falls_back():
    assert pick_closest_ratio(100, 0) == "1:1"
