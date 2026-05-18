import logging
import os
import tempfile
from typing import Optional

from PIL import Image

logger = logging.getLogger(__name__)

MAX_BEAUTIFIED_BYTES = 8 * 1024 * 1024


def _save_image(img: Image.Image, path: str, fmt: str, *, quality: Optional[int] = None) -> None:
    save_kw: dict = {}
    if quality is not None and fmt == "JPEG":
        save_kw["quality"] = quality
        save_kw["optimize"] = True
    exif = img.info.get("exif")
    if exif:
        save_kw["exif"] = exif
    img.save(path, format=fmt, **save_kw)


def resize_to_max_bytes(path: str, max_bytes: int = MAX_BEAUTIFIED_BYTES) -> None:
    """若文件超过 max_bytes，等比缩放并必要时降低 JPEG 质量，覆盖原路径。"""
    if os.path.getsize(path) <= max_bytes:
        return

    dirname = os.path.dirname(path) or "."
    suffix = os.path.splitext(path)[1] or ".png"

    with Image.open(path) as img:
        fmt = (img.format or "PNG").upper()
        if fmt == "JPG":
            fmt = "JPEG"

        def write_candidate(image: Image.Image, out_fmt: str, quality: Optional[int] = None) -> bool:
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=suffix, dir=dirname
            ) as tmp:
                temp_path = tmp.name
            try:
                _save_image(image, temp_path, out_fmt, quality=quality)
                if os.path.getsize(temp_path) <= max_bytes:
                    os.replace(temp_path, path)
                    return True
            finally:
                if os.path.exists(temp_path) and os.path.abspath(temp_path) != os.path.abspath(
                    path
                ):
                    try:
                        os.remove(temp_path)
                    except OSError:
                        pass
            return False

        if fmt == "JPEG":
            for quality in (90, 80, 70, 60):
                if write_candidate(img, "JPEG", quality=quality):
                    logger.info("resized beautified image (jpeg quality) path=%s", path)
                    return

        working = img.copy()
        for _ in range(5):
            if write_candidate(working, fmt, quality=85 if fmt == "JPEG" else None):
                logger.info("resized beautified image path=%s", path)
                return
            w, h = working.size
            target_w = max(1024, int(w * 0.85))
            target_h = max(1024, int(h * 0.85))
            if target_w >= w and target_h >= h:
                break
            working = working.resize((target_w, target_h), Image.Resampling.LANCZOS)

        rgb = working.convert("RGB")
        if write_candidate(rgb, "JPEG", quality=80):
            logger.info("resized beautified image (fallback jpeg) path=%s", path)
            return

    if os.path.getsize(path) > max_bytes:
        raise RuntimeError("美化结果缩放后仍超过大小限制")
