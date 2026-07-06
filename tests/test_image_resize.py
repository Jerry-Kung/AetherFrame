"""image_resize 工具边界测试。"""

import os

import pytest
from PIL import Image

from app.utils.image_resize import MAX_BEAUTIFIED_BYTES, resize_to_max_bytes


def _write_png(path: str, size: tuple[int, int], color=(255, 0, 0)) -> None:
    Image.new("RGB", size, color).save(path, format="PNG")


def test_resize_skips_when_under_limit(tmp_path):
    path = str(tmp_path / "small.png")
    _write_png(path, (64, 64))
    before = os.path.getsize(path)
    resize_to_max_bytes(path, max_bytes=MAX_BEAUTIFIED_BYTES)
    assert os.path.getsize(path) == before


def test_resize_shrinks_large_jpeg(tmp_path):
    path = str(tmp_path / "large.jpg")
    img = Image.effect_noise((5000, 5000), 128).convert("RGB")
    img.save(path, format="JPEG", quality=95)
    assert os.path.getsize(path) > MAX_BEAUTIFIED_BYTES
    resize_to_max_bytes(path, max_bytes=MAX_BEAUTIFIED_BYTES)
    assert os.path.getsize(path) <= MAX_BEAUTIFIED_BYTES
