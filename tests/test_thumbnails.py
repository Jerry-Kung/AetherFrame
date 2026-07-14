"""缩略图工具单测:生成、跳过小图、过期重建、损坏回退、删除。"""
import os
import time

from PIL import Image

from app.utils.thumbnails import (
    THUMB_MAX_EDGE,
    delete_thumbnail_for,
    get_or_create_thumbnail,
    thumbnail_path_for,
)


def _write_png(path: str, w: int, h: int) -> None:
    Image.new("RGB", (w, h), (200, 80, 120)).save(path, format="PNG")


def test_large_image_generates_webp_thumbnail(tmp_path):
    src = str(tmp_path / "big.png")
    _write_png(src, 1600, 900)

    thumb = get_or_create_thumbnail(src)

    assert thumb == thumbnail_path_for(src)
    assert os.path.isfile(thumb)
    assert thumb.endswith(".webp")
    assert os.path.basename(os.path.dirname(thumb)) == ".thumbs"
    with Image.open(thumb) as im:
        assert max(im.size) == THUMB_MAX_EDGE
        assert im.format == "WEBP"
    # 缩略图应显著小于原图
    assert os.path.getsize(thumb) < os.path.getsize(src)


def test_small_image_returns_none(tmp_path):
    src = str(tmp_path / "small.png")
    _write_png(src, 400, 300)

    assert get_or_create_thumbnail(src) is None
    assert not os.path.isfile(thumbnail_path_for(src))


def test_cached_thumbnail_is_reused(tmp_path):
    src = str(tmp_path / "big.png")
    _write_png(src, 1600, 900)
    first = get_or_create_thumbnail(src)
    first_mtime = os.path.getmtime(first)

    second = get_or_create_thumbnail(src)

    assert second == first
    assert os.path.getmtime(second) == first_mtime


def test_stale_thumbnail_is_regenerated(tmp_path):
    src = str(tmp_path / "big.png")
    _write_png(src, 1600, 900)
    thumb = get_or_create_thumbnail(src)
    # 把缩略图 mtime 拨回过去,模拟原图被覆盖更新
    past = time.time() - 3600
    os.utime(thumb, (past, past))
    _write_png(src, 1200, 1200)

    regenerated = get_or_create_thumbnail(src)

    assert regenerated == thumb
    with Image.open(regenerated) as im:
        assert im.size == (THUMB_MAX_EDGE, THUMB_MAX_EDGE)


def test_corrupt_image_returns_none(tmp_path):
    src = str(tmp_path / "broken.png")
    with open(src, "wb") as f:
        f.write(b"not an image at all")

    assert get_or_create_thumbnail(src) is None


def test_rgba_png_keeps_alpha(tmp_path):
    src = str(tmp_path / "alpha.png")
    Image.new("RGBA", (1024, 1024), (200, 80, 120, 128)).save(src, format="PNG")

    thumb = get_or_create_thumbnail(src)

    with Image.open(thumb) as im:
        assert im.mode in ("RGBA", "LA")


def test_delete_thumbnail_for(tmp_path):
    src = str(tmp_path / "big.png")
    _write_png(src, 1600, 900)
    thumb = get_or_create_thumbnail(src)
    assert os.path.isfile(thumb)

    delete_thumbnail_for(src)

    assert not os.path.isfile(thumb)
    # 幂等:再删不抛异常
    delete_thumbnail_for(src)
