"""
图片缩略图工具(惰性生成)。

- 缩略图存放在原图同目录的 .thumbs/ 子目录下,文件名 <原图stem>.webp;
- 首次请求时生成,原图 mtime 晚于缩略图时自动重建(覆盖头像等固定文件名场景);
- 原图最长边 ≤ THUMB_MAX_EDGE 时不生成(返回 None,调用方回退原图,避免放大);
- 任何异常(损坏文件、不支持格式)都回退 None,图片路由永远有原图兜底。
"""
from __future__ import annotations

import logging
import os
import tempfile
from typing import Optional

from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

THUMB_DIR_NAME = ".thumbs"
THUMB_MAX_EDGE = 512
THUMB_WEBP_QUALITY = 82


def thumbnail_path_for(src_path: str) -> str:
    d = os.path.dirname(src_path)
    stem = os.path.splitext(os.path.basename(src_path))[0]
    return os.path.join(d, THUMB_DIR_NAME, f"{stem}.webp")


def get_or_create_thumbnail(src_path: str) -> Optional[str]:
    """返回缩略图路径;原图已够小或生成失败时返回 None。"""
    try:
        thumb_path = thumbnail_path_for(src_path)
        src_mtime = os.path.getmtime(src_path)
        if os.path.isfile(thumb_path) and os.path.getmtime(thumb_path) >= src_mtime:
            return thumb_path

        with Image.open(src_path) as im:
            if max(im.size) <= THUMB_MAX_EDGE:
                return None
            im = ImageOps.exif_transpose(im)
            has_alpha = im.mode in ("RGBA", "LA") or (
                im.mode == "P" and "transparency" in im.info
            )
            im = im.convert("RGBA" if has_alpha else "RGB")
            im.thumbnail((THUMB_MAX_EDGE, THUMB_MAX_EDGE), Image.LANCZOS)

            os.makedirs(os.path.dirname(thumb_path), exist_ok=True)
            # 先写临时文件再原子替换,避免并发请求读到半截文件
            fd, tmp = tempfile.mkstemp(
                suffix=".webp", dir=os.path.dirname(thumb_path)
            )
            try:
                with os.fdopen(fd, "wb") as f:
                    im.save(f, format="WEBP", quality=THUMB_WEBP_QUALITY, method=4)
                os.replace(tmp, thumb_path)
            except BaseException:
                try:
                    os.remove(tmp)
                except OSError:
                    pass
                raise
        return thumb_path
    except Exception as e:
        logger.warning("生成缩略图失败,回退原图 %s: %s", src_path, e)
        return None


def delete_thumbnail_for(src_path: str) -> None:
    """删除原图对应的缩略图(幂等,失败仅告警)。"""
    try:
        p = thumbnail_path_for(src_path)
        if os.path.isfile(p):
            os.remove(p)
    except OSError as e:
        logger.warning("删除缩略图失败 %s: %s", src_path, e)
