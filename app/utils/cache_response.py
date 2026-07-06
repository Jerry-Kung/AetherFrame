"""
图片端点的 HTTP 缓存响应工具。

- build_immutable_file_response: URL 内容寻址型资源（文件名变化即 URL 变化），
  返回一年期的 immutable 强缓存。
- build_revalidate_file_response: URL 不变但内容会被覆盖的资源（如固定文件名头像、
  按 shot_type 命名的标准照槽位、修补任务复用文件名的主图/参考图/结果图），
  使用基于 ETag + Last-Modified 的协商缓存；命中条件请求时返回 304。

注：Starlette 的 FileResponse 会自动设置 ETag/Last-Modified，但不会自动比对
请求里的 If-None-Match / If-Modified-Since。所以这里在路由层手动比对，
命中即返回 304（无 body）。
"""
from __future__ import annotations

import hashlib
import os
from email.utils import formatdate, parsedate_to_datetime
from typing import Optional

from fastapi import Request
from fastapi.responses import FileResponse, Response


_MEDIA_TYPE_MAP = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}

IMMUTABLE_CACHE_CONTROL = "public, max-age=31536000, immutable"
REVALIDATE_CACHE_CONTROL = "public, max-age=0, must-revalidate"


def guess_media_type(filename_or_path: str) -> str:
    ext = os.path.splitext(filename_or_path)[1].lower()
    return _MEDIA_TYPE_MAP.get(ext, "application/octet-stream")


def _file_validators(path: str) -> tuple[str, str]:
    """根据文件 mtime + size 计算 ETag 与 Last-Modified（与 Starlette 一致）。"""
    st = os.stat(path)
    etag_base = f"{st.st_mtime}-{st.st_size}"
    etag = f'"{hashlib.md5(etag_base.encode(), usedforsecurity=False).hexdigest()}"'
    last_modified = formatdate(st.st_mtime, usegmt=True)
    return etag, last_modified


def _if_none_match_hits(if_none_match: Optional[str], etag: str) -> bool:
    if not if_none_match:
        return False
    if if_none_match.strip() == "*":
        return True
    for item in if_none_match.split(","):
        candidate = item.strip()
        if not candidate:
            continue
        if candidate.startswith("W/"):
            candidate = candidate[2:].strip()
        if candidate == etag:
            return True
    return False


def _if_modified_since_hits(if_modified_since: Optional[str], last_modified: str) -> bool:
    if not if_modified_since:
        return False
    try:
        ims_dt = parsedate_to_datetime(if_modified_since)
        lm_dt = parsedate_to_datetime(last_modified)
    except (TypeError, ValueError):
        return False
    if ims_dt is None or lm_dt is None:
        return False
    return lm_dt <= ims_dt


def build_immutable_file_response(
    path: str,
    filename: str,
    media_type: Optional[str] = None,
) -> FileResponse:
    """URL 内容寻址型资源：一年 immutable 强缓存。"""
    return FileResponse(
        path=path,
        media_type=media_type or guess_media_type(filename),
        filename=filename,
        headers={"Cache-Control": IMMUTABLE_CACHE_CONTROL},
    )


def build_revalidate_file_response(
    request: Request,
    path: str,
    filename: str,
    media_type: Optional[str] = None,
) -> Response:
    """URL 不变内容可变型资源：协商缓存；命中条件请求返回 304。"""
    etag, last_modified = _file_validators(path)

    if _if_none_match_hits(
        request.headers.get("if-none-match"), etag
    ) or _if_modified_since_hits(
        request.headers.get("if-modified-since"), last_modified
    ):
        return Response(
            status_code=304,
            headers={
                "Cache-Control": REVALIDATE_CACHE_CONTROL,
                "ETag": etag,
                "Last-Modified": last_modified,
            },
        )

    return FileResponse(
        path=path,
        media_type=media_type or guess_media_type(filename),
        filename=filename,
        headers={"Cache-Control": REVALIDATE_CACHE_CONTROL},
    )
