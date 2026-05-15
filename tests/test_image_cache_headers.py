"""
图片端点 HTTP 缓存响应测试。

覆盖：
- helper 函数：build_immutable_file_response 与 build_revalidate_file_response
- 协商缓存的 If-None-Match / If-Modified-Since 命中 → 304
- ETag 失配 / If-Modified-Since 早于文件 mtime → 200
- 端点级冒烟：material/raw、material/avatar、creation/quick-create、material/result-images（保持 no-store）
"""
import os
import tempfile
from email.utils import formatdate

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.utils.cache_response import (
    IMMUTABLE_CACHE_CONTROL,
    REVALIDATE_CACHE_CONTROL,
    _file_validators,
    _if_modified_since_hits,
    _if_none_match_hits,
    build_immutable_file_response,
    build_revalidate_file_response,
    guess_media_type,
)


# ==========================================
# Fixtures
# ==========================================


@pytest.fixture
def png_file():
    """创建一个临时 PNG 文件，用于喂给 FileResponse。"""
    fd, path = tempfile.mkstemp(suffix=".png")
    try:
        with os.fdopen(fd, "wb") as f:
            # 极简 1x1 透明 PNG
            f.write(
                bytes.fromhex(
                    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
                    "0000000d49444154789c6300010000000500015b3fa6c20000000049454e44ae426082"
                )
            )
        yield path
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


@pytest.fixture
def helper_app(png_file):
    """构建仅用于测试 helper 的最小 FastAPI 应用。"""
    app = FastAPI()

    @app.get("/immutable")
    def _immutable():
        return build_immutable_file_response(path=png_file, filename="x.png")

    @app.get("/revalidate")
    def _revalidate(request: Request):
        return build_revalidate_file_response(
            request=request, path=png_file, filename="x.png"
        )

    return TestClient(app)


# ==========================================
# 工具函数：媒体类型映射
# ==========================================


class TestGuessMediaType:
    def test_png(self):
        assert guess_media_type("a.png") == "image/png"

    def test_jpg_and_jpeg(self):
        assert guess_media_type("a.jpg") == "image/jpeg"
        assert guess_media_type("a.JPEG") == "image/jpeg"

    def test_webp(self):
        assert guess_media_type("a.webp") == "image/webp"

    def test_gif(self):
        assert guess_media_type("a.gif") == "image/gif"

    def test_unknown_falls_back(self):
        assert guess_media_type("a.bin") == "application/octet-stream"
        assert guess_media_type("noext") == "application/octet-stream"


# ==========================================
# 工具函数：条件请求比对
# ==========================================


class TestIfNoneMatch:
    def test_empty_returns_false(self):
        assert _if_none_match_hits(None, '"abc"') is False
        assert _if_none_match_hits("", '"abc"') is False

    def test_exact_match(self):
        assert _if_none_match_hits('"abc"', '"abc"') is True

    def test_weak_etag_match(self):
        assert _if_none_match_hits('W/"abc"', '"abc"') is True

    def test_wildcard(self):
        assert _if_none_match_hits("*", '"anything"') is True

    def test_multiple_etags(self):
        assert _if_none_match_hits('"x", "abc", "y"', '"abc"') is True

    def test_mismatch(self):
        assert _if_none_match_hits('"other"', '"abc"') is False


class TestIfModifiedSince:
    def test_empty_returns_false(self):
        assert _if_modified_since_hits(None, formatdate(1700000000, usegmt=True)) is False

    def test_same_or_newer_hits(self):
        # IMS == LM
        lm = formatdate(1700000000, usegmt=True)
        assert _if_modified_since_hits(lm, lm) is True

    def test_older_ims_misses(self):
        lm = formatdate(1700001000, usegmt=True)
        ims = formatdate(1700000000, usegmt=True)  # 客户端持有的版本更老
        assert _if_modified_since_hits(ims, lm) is False

    def test_invalid_date(self):
        assert _if_modified_since_hits("garbage", formatdate(1700000000, usegmt=True)) is False


# ==========================================
# 端到端：immutable 响应
# ==========================================


class TestImmutableResponse:
    def test_returns_immutable_cache_control(self, helper_app):
        r = helper_app.get("/immutable")
        assert r.status_code == 200
        assert r.headers["cache-control"] == IMMUTABLE_CACHE_CONTROL

    def test_carries_body(self, helper_app):
        r = helper_app.get("/immutable")
        assert len(r.content) > 0

    def test_immutable_ignores_if_none_match(self, helper_app):
        # immutable 响应即使带 ETag/If-None-Match，也应该返 200（我们没主动比对）
        # 行为契约：客户端在 max-age 内根本不会发请求；万一发了，返 200 也安全。
        r = helper_app.get("/immutable", headers={"If-None-Match": "*"})
        assert r.status_code == 200


# ==========================================
# 端到端：协商缓存响应
# ==========================================


class TestRevalidateResponse:
    def test_first_request_returns_200_with_validators(self, helper_app):
        r = helper_app.get("/revalidate")
        assert r.status_code == 200
        assert r.headers["cache-control"] == REVALIDATE_CACHE_CONTROL
        assert "etag" in r.headers
        assert "last-modified" in r.headers
        assert len(r.content) > 0

    def test_if_none_match_hit_returns_304(self, helper_app):
        first = helper_app.get("/revalidate")
        etag = first.headers["etag"]

        r = helper_app.get("/revalidate", headers={"If-None-Match": etag})
        assert r.status_code == 304
        assert r.headers["cache-control"] == REVALIDATE_CACHE_CONTROL
        assert r.headers["etag"] == etag
        # 304 不应带 body
        assert r.content == b""

    def test_if_none_match_miss_returns_200(self, helper_app):
        r = helper_app.get("/revalidate", headers={"If-None-Match": '"stale-value"'})
        assert r.status_code == 200
        assert len(r.content) > 0

    def test_if_modified_since_hit_returns_304(self, helper_app, png_file):
        _etag, last_modified = _file_validators(png_file)
        r = helper_app.get(
            "/revalidate", headers={"If-Modified-Since": last_modified}
        )
        assert r.status_code == 304
        assert r.content == b""

    def test_if_modified_since_older_returns_200(self, helper_app):
        # 1970 年的日期肯定早于文件 mtime → 应当返 200
        old = formatdate(0, usegmt=True)
        r = helper_app.get("/revalidate", headers={"If-Modified-Since": old})
        assert r.status_code == 200

    def test_etag_changes_after_file_modified(self, helper_app, png_file):
        first_etag = helper_app.get("/revalidate").headers["etag"]
        # 修改文件内容（mtime + size 任一变化都应导致 ETag 变化）
        with open(png_file, "ab") as f:
            f.write(b"\x00")
        # mtime 精度不一定到微秒，强制让 mtime 推进
        st = os.stat(png_file)
        os.utime(png_file, (st.st_atime, st.st_mtime + 1))
        second = helper_app.get("/revalidate")
        assert second.headers["etag"] != first_etag


# ==========================================
# 端到端：业务路由冒烟（基于 app.main:app）
# ==========================================


@pytest.fixture(scope="module")
def real_client():
    from app.main import app

    return TestClient(app)


class TestMaterialRawImageEndpoint:
    """A 端点：内容寻址 → immutable。"""

    def test_404_for_missing_character(self, real_client):
        r = real_client.get(
            "/api/material/characters/mchar_nope/images/raw/missing.png"
        )
        assert r.status_code == 404


class TestMaterialAvatarEndpoint:
    """B 端点：固定文件名 avatar.png → 协商缓存。"""

    def test_404_for_missing_avatar(self, real_client):
        r = real_client.get(
            "/api/material/characters/mchar_nope/images/avatar/avatar.png"
        )
        assert r.status_code == 404


class TestStandardSlotEndpoint:
    """D 端点：协商缓存；先校验 shot_type 校验逻辑没回归。"""

    def test_invalid_shot_type_returns_404(self, real_client):
        r = real_client.get(
            "/api/material/characters/mchar_x/standard-photo/slot-images/invalid_type"
        )
        assert r.status_code == 404


class TestStandardResultImageEndpoint:
    """C 端点：必须保持 no-store 不变（文件不存在路径走不到响应头，
    所以这里只用单元测试在 helper 之外的约束反向校验：源码里仍是 no-store）。"""

    def test_source_keeps_no_store(self):
        """通过读源码确保 no-store 没被误删。"""
        import inspect

        from app.routes import material

        src = inspect.getsource(material.get_standard_photo_result_image)
        assert "no-store" in src


class TestRepairImageEndpoint:
    """E 端点：协商缓存。"""

    def test_invalid_image_type_returns_400(self, real_client):
        r = real_client.get("/api/repair/tasks/task_x/images/invalid/file.png")
        assert r.status_code == 400


class TestQuickCreateImageEndpoint:
    """F 端点：内容寻址（带微秒时间戳）→ immutable。"""

    def test_404_for_missing_task(self, real_client):
        r = real_client.get(
            "/api/creation/quick-create/tasks/qct_nope/images/missing.png"
        )
        assert r.status_code == 404
