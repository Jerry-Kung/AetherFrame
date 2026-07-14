# 图片缩略图机制实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 列表/网格/卡片场景改用服务端按需生成的 ~512px WebP 缩略图,把素材加工页冷缓存打开时 ~12MB 的图片负载降到 ~0.5MB,消除十几秒的加载卡顿;点开大图预览仍用原图。

**Architecture:** 后端新增惰性缩略图工具(首次请求时用 Pillow 生成 `<原图目录>/.thumbs/<stem>.webp`,mtime 过期自动重建,失败/原图已够小时回退原图);4 个图片路由增加 `variant=thumb` 查询参数;前端新增 `thumbUrl()` 工具函数,在小尺寸展示的 `<img>` 上包一层。无 DB 变更、无启动期回填(按需生成天然覆盖存量)。

**Tech Stack:** FastAPI + Pillow(requirements.txt 已有 `Pillow>=10.0.0`)、React + TypeScript、pytest。

## Global Constraints

- 不引入新依赖、不做 DB 迁移。
- 缩略图规格:最长边 512px、WebP quality 82;原图最长边 ≤512px 时直接回退原图(不放大)。
- 缓存语义与原路由一致:内容寻址 URL(raw 参考图、quick-create 结果图)缩略图用 `immutable` 强缓存;固定文件名 URL(头像、标准照槽位)缩略图用 ETag 协商缓存(ETag 基于缩略图文件,原图更新→缩略图重建→ETag 变化)。
- 以下场景**必须保持原图**,不得替换:`ImagePreviewModal` 大图预览、`AvatarPickerModal` 裁剪画布(line ~230)、`PhotoTaskPage` 标准照候选图与预览(质量评审)、`ImageFeedbackModal`(feedback 需检查腿脚细节,是核心质检依据)。
- 后端注释/日志/提交信息用中文,风格与现有代码一致。提交 scope 参考近期历史:`feat(material)` / `feat(creation)` / `feat(page)`。
- 每个任务完成后运行 `pytest tests/ -x -q`(后端)或 `cd page && npm run type-check && npm run lint`(前端),全绿再提交。
- 前端 React hooks 必须显式 import(repo 约定,type-check 不认 auto-import)。

---

### Task 1: 后端缩略图工具 `app/utils/thumbnails.py`

**Files:**
- Create: `app/utils/thumbnails.py`
- Test: `tests/test_thumbnails.py`

**Interfaces:**
- Produces: `get_or_create_thumbnail(src_path: str) -> Optional[str]`(返回缩略图绝对路径;原图已够小或生成失败返回 `None`,调用方回退原图)、`thumbnail_path_for(src_path: str) -> str`、`delete_thumbnail_for(src_path: str) -> None`。Task 2/3 的路由消费这些函数。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_thumbnails.py
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
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/test_thumbnails.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'app.utils.thumbnails'`

- [ ] **Step 3: 实现 `app/utils/thumbnails.py`**

```python
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
```

- [ ] **Step 4: 运行确认通过**

Run: `pytest tests/test_thumbnails.py -v`
Expected: 7 项全部 PASS

- [ ] **Step 5: 全量回归 + 提交**

Run: `pytest tests/ -x -q`
Expected: 全绿

```bash
git add app/utils/thumbnails.py tests/test_thumbnails.py
git commit -m "feat(utils): 惰性图片缩略图工具(512px WebP,mtime 过期重建,失败回退原图)"
```

---

### Task 2: material 图片路由支持 `variant=thumb`(raw 参考图 + 头像)+ 删除时清理缩略图

**Files:**
- Modify: `app/routes/material.py`(`get_raw_image` 约 line 598-608、`get_avatar_image` 约 line 611-622)
- Modify: `app/services/material_service/material_file_service.py`(`delete_raw_image_file` 约 line 302、`_clear_avatar_dir_files` 约 line 235)
- Test: `tests/routes/test_image_thumb_variant.py`

**Interfaces:**
- Consumes: Task 1 的 `get_or_create_thumbnail` / `delete_thumbnail_for`。
- Produces: `GET /api/material/characters/{id}/images/raw/{filename}?variant=thumb`(immutable 缓存,`image/webp`)、`GET /api/material/characters/{id}/images/avatar/{filename}?variant=thumb`(协商缓存)。无 `variant` 或缩略图不可用时行为与现状完全一致。前端 Task 4 依赖此查询参数。

- [ ] **Step 1: 写失败测试**

```python
# tests/routes/test_image_thumb_variant.py
"""图片路由 variant=thumb:缩略图返回、原图回退、缓存头。"""
import os
import uuid

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.models.material import MaterialCharacter, MaterialCharacterRawImage


@pytest.fixture
def api_client(db_session):
    from app.main import app
    from app.models.database import get_db

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _create_character(db_session) -> str:
    char_id = f"mchar_{uuid.uuid4().hex[:10]}"
    db_session.add(
        MaterialCharacter(
            id=char_id, name="Thumb", display_name="Thumb", status="idle", setting_text=""
        )
    )
    db_session.commit()
    return char_id


def _add_raw_image(db_session, char_id: str, w: int, h: int) -> str:
    """写入 raw/official 下的真实 PNG + DB 行,返回 stored_filename。"""
    from app.services.material_service import material_file_service as mfs

    image_id = str(uuid.uuid4())
    stored = f"{image_id}.png"
    mfs.ensure_character_dirs(char_id)
    path = os.path.join(mfs.get_character_raw_type_dir(char_id, "official"), stored)
    Image.new("RGB", (w, h), (200, 80, 120)).save(path, format="PNG")
    db_session.add(
        MaterialCharacterRawImage(
            id=image_id,
            character_id=char_id,
            stored_filename=stored,
            type="official",
            tags_json="[]",
        )
    )
    db_session.commit()
    return stored


def test_raw_image_thumb_variant_returns_webp(api_client, db_session):
    char_id = _create_character(db_session)
    stored = _add_raw_image(db_session, char_id, 1600, 900)

    full = api_client.get(f"/api/material/characters/{char_id}/images/raw/{stored}")
    thumb = api_client.get(
        f"/api/material/characters/{char_id}/images/raw/{stored}?variant=thumb"
    )

    assert full.status_code == 200 and thumb.status_code == 200
    assert thumb.headers["content-type"] == "image/webp"
    assert "immutable" in thumb.headers["cache-control"]
    assert len(thumb.content) < len(full.content)


def test_raw_image_thumb_falls_back_when_small(api_client, db_session):
    char_id = _create_character(db_session)
    stored = _add_raw_image(db_session, char_id, 300, 200)

    thumb = api_client.get(
        f"/api/material/characters/{char_id}/images/raw/{stored}?variant=thumb"
    )

    assert thumb.status_code == 200
    assert thumb.headers["content-type"] == "image/png"  # 回退原图


def test_raw_image_without_variant_unchanged(api_client, db_session):
    char_id = _create_character(db_session)
    stored = _add_raw_image(db_session, char_id, 1600, 900)

    r = api_client.get(f"/api/material/characters/{char_id}/images/raw/{stored}")

    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"


def test_avatar_thumb_variant_returns_webp_with_etag(api_client, db_session):
    from app.services.material_service import material_file_service as mfs

    char_id = _create_character(db_session)
    mfs.ensure_character_dirs(char_id)
    avatar_path = os.path.join(mfs.get_character_avatar_dir(char_id), "avatar.png")
    Image.new("RGB", (1024, 1024), (80, 120, 200)).save(avatar_path, format="PNG")

    thumb = api_client.get(
        f"/api/material/characters/{char_id}/images/avatar/avatar.png?variant=thumb"
    )

    assert thumb.status_code == 200
    assert thumb.headers["content-type"] == "image/webp"
    assert thumb.headers.get("etag")
    # 协商缓存:带 If-None-Match 再请求应 304
    r304 = api_client.get(
        f"/api/material/characters/{char_id}/images/avatar/avatar.png?variant=thumb",
        headers={"If-None-Match": thumb.headers["etag"]},
    )
    assert r304.status_code == 304


def test_delete_raw_image_also_deletes_thumbnail(api_client, db_session):
    from app.services.material_service import material_file_service as mfs
    from app.utils.thumbnails import thumbnail_path_for

    char_id = _create_character(db_session)
    stored = _add_raw_image(db_session, char_id, 1600, 900)
    api_client.get(
        f"/api/material/characters/{char_id}/images/raw/{stored}?variant=thumb"
    )
    src = os.path.join(mfs.get_character_raw_type_dir(char_id, "official"), stored)
    assert os.path.isfile(thumbnail_path_for(src))

    assert mfs.delete_raw_image_file(char_id, stored, "official") is True

    assert not os.path.isfile(thumbnail_path_for(src))
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/routes/test_image_thumb_variant.py -v`
Expected: thumb 相关断言 FAIL(`content-type` 仍为 `image/png` / 缩略图文件不存在)

- [ ] **Step 3: 修改 `app/routes/material.py` 两个路由**

在文件顶部 import 区加入:

```python
from app.utils.thumbnails import get_or_create_thumbnail
```

`get_raw_image` 改为:

```python
@router.get("/characters/{character_id}/images/raw/{filename}")
def get_raw_image(
    character_id: str,
    filename: str,
    variant: Optional[str] = Query(None, description="thumb=返回 512px WebP 缩略图"),
    service: MaterialService = Depends(get_material_service),
):
    logger.debug(f"API 请求 - 读取参考图: {character_id}/{filename}")
    path = service.get_raw_image_path(character_id, filename)
    if not path:
        raise HTTPException(status_code=404, detail="文件不存在")
    if variant == "thumb":
        thumb = get_or_create_thumbnail(path)
        if thumb:
            # URL 内容寻址(variant 参与缓存键),缩略图同样可用 immutable
            return build_immutable_file_response(
                path=thumb, filename=os.path.basename(thumb), media_type="image/webp"
            )
    return build_immutable_file_response(path=path, filename=filename)
```

`get_avatar_image` 改为:

```python
@router.get("/characters/{character_id}/images/avatar/{filename}")
def get_avatar_image(
    character_id: str,
    filename: str,
    request: Request,
    variant: Optional[str] = Query(None, description="thumb=返回 512px WebP 缩略图"),
    service: MaterialService = Depends(get_material_service),
):
    logger.debug(f"API 请求 - 读取角色头像: {character_id}/{filename}")
    path = service.get_avatar_image_path(character_id, filename)
    if not path:
        raise HTTPException(status_code=404, detail="文件不存在")
    if variant == "thumb":
        thumb = get_or_create_thumbnail(path)
        if thumb:
            # 头像 URL 固定文件名,协商缓存;ETag 基于缩略图文件,原图更新会触发重建→ETag 变化
            return build_revalidate_file_response(
                request=request,
                path=thumb,
                filename=os.path.basename(thumb),
                media_type="image/webp",
            )
    return build_revalidate_file_response(request=request, path=path, filename=filename)
```

- [ ] **Step 4: 修改 `material_file_service.py` 清理缩略图**

文件顶部加 import:

```python
from app.utils.thumbnails import delete_thumbnail_for
```

`delete_raw_image_file` 中,两处 `delete_file(...)` 成功前先解析路径删缩略图 —— 整函数替换为:

```python
def delete_raw_image_file(character_id: str, stored_filename: str, raw_image_type: str = "official") -> bool:
    """删除 raw 目录下单张参考图文件(连同缩略图)。"""
    image_type = raw_image_type if raw_image_type in RAW_IMAGE_TYPES else "official"
    src = get_raw_image_path(character_id, stored_filename, image_type)
    if src:
        delete_thumbnail_for(src)
    typed_dir = get_character_raw_type_dir(character_id, image_type)
    try:
        if delete_file(typed_dir, stored_filename):
            return True
        # 兼容旧目录
        return delete_file(get_character_raw_dir(character_id), stored_filename)
    except FileDeleteError as e:
        logger.warning(f"删除参考图文件失败: {e}")
        return False
```

`_clear_avatar_dir_files` 的 `os.remove(path)` 前一行加:

```python
                delete_thumbnail_for(path)
```

(即换头像时旧头像的缩略图一并清掉;`.thumbs` 目录本身因 `os.path.isfile` 判断天然被跳过。)

- [ ] **Step 5: 运行确认通过 + 全量回归**

Run: `pytest tests/routes/test_image_thumb_variant.py -v && pytest tests/ -x -q`
Expected: 全绿

- [ ] **Step 6: 提交**

```bash
git add app/routes/material.py app/services/material_service/material_file_service.py tests/routes/test_image_thumb_variant.py
git commit -m "feat(material): 参考图/头像路由支持 variant=thumb 缩略图,删除时联动清理"
```

---

### Task 3: 标准照槽位 + 灵感产线结果图路由支持 `variant=thumb`

**Files:**
- Modify: `app/routes/material.py`(`get_standard_slot_image` 约 line 965-983)
- Modify: `app/routes/creation.py`(`get_quick_create_image` 约 line 611-624)
- Test: `tests/routes/test_image_thumb_variant.py`(追加 2 个用例)

**Interfaces:**
- Consumes: Task 1 的 `get_or_create_thumbnail`;Task 2 已在 material.py 加好 import。
- Produces: `GET /api/material/characters/{id}/standard-photo/slot-images/{shot_type}?variant=thumb`(协商缓存)、`GET /api/creation/quick-create/tasks/{task_id}/images/{path}?variant=thumb`(immutable)。前端 Task 4 依赖。

- [ ] **Step 1: 追加失败测试**

在 `tests/routes/test_image_thumb_variant.py` 末尾追加:

```python
def test_standard_slot_image_thumb_variant(api_client, db_session):
    from app.services.material_service import material_file_service as mfs

    char_id = _create_character(db_session)
    mfs.ensure_character_dirs(char_id)
    slot_dir = mfs.get_standard_photo_slot_dir(char_id)
    os.makedirs(slot_dir, exist_ok=True)
    Image.new("RGB", (1280, 720), (10, 200, 100)).save(
        os.path.join(slot_dir, "full_front.png"), format="PNG"
    )

    thumb = api_client.get(
        f"/api/material/characters/{char_id}/standard-photo/slot-images/full_front?variant=thumb"
    )

    assert thumb.status_code == 200
    assert thumb.headers["content-type"] == "image/webp"


def test_quick_create_image_thumb_variant(api_client, db_session, temp_data_dir):
    from app.models.creation import CreationQuickCreateTask

    task_id = f"qct_{uuid.uuid4().hex[:10]}"
    work_dir = os.path.join(temp_data_dir, "beautify", "quick_create", task_id)
    os.makedirs(work_dir, exist_ok=True)
    Image.new("RGB", (1920, 1080), (120, 60, 200)).save(
        os.path.join(work_dir, "result_0.png"), format="PNG"
    )
    db_session.add(
        CreationQuickCreateTask(
            id=task_id,
            status="completed",
            work_dir=work_dir,
        )
    )
    db_session.commit()

    thumb = api_client.get(
        f"/api/creation/quick-create/tasks/{task_id}/images/result_0.png?variant=thumb"
    )

    assert thumb.status_code == 200
    assert thumb.headers["content-type"] == "image/webp"
    assert "immutable" in thumb.headers["cache-control"]
```

注意:`CreationQuickCreateTask` 的必填列以 `app/models/creation.py` 实际定义为准 —— 先读该模型,若有其他 `nullable=False` 且无默认值的列(如 `seed_prompt`、`aspect_ratio` 等),在构造时补上空串/合理默认值,使 INSERT 通过;这是测试数据构造问题,不改产品代码。

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/routes/test_image_thumb_variant.py -v -k "slot or quick"`
Expected: FAIL(`content-type` 为 `image/png`)

- [ ] **Step 3: 修改两个路由**

`app/routes/material.py` 的 `get_standard_slot_image` 改为:

```python
@router.get("/characters/{character_id}/standard-photo/slot-images/{shot_type}")
def get_standard_slot_image(
    character_id: str,
    shot_type: str,
    request: Request,
    variant: Optional[str] = Query(None, description="thumb=返回 512px WebP 缩略图"),
    service: MaterialService = Depends(get_material_service),
):
    """已保存的正式标准参考图(按类型槽位存储,与当前生成任务目录无关)。"""
    if shot_type not in SHOT_TYPE_TO_INDEX:
        raise HTTPException(status_code=404, detail="标准照类型无效")
    path = service.get_standard_slot_image_path(character_id, shot_type)
    if not path:
        raise HTTPException(status_code=404, detail="文件不存在")
    if variant == "thumb":
        thumb = get_or_create_thumbnail(path)
        if thumb:
            # 槽位 URL 固定,协商缓存;槽位被覆盖保存→缩略图重建→ETag 变化
            return build_revalidate_file_response(
                request=request,
                path=thumb,
                filename=f"{shot_type}.webp",
                media_type="image/webp",
            )
    return build_revalidate_file_response(
        request=request,
        path=path,
        filename=f"{shot_type}.png",
        media_type="image/png",
    )
```

`app/routes/creation.py`:顶部 import 区加

```python
from app.utils.thumbnails import get_or_create_thumbnail
```

`get_quick_create_image` 改为(注意该文件需已有 `Query` import,没有则从 fastapi 补):

```python
@router.get("/quick-create/tasks/{task_id}/images/{image_path:path}")
def get_quick_create_image(
    task_id: str,
    image_path: str,
    variant: Optional[str] = Query(None, description="thumb=返回 512px WebP 缩略图"),
    service: QuickCreateService = Depends(get_quick_create_service),
):
    tid = (task_id or "").strip()
    if not tid:
        raise HTTPException(status_code=400, detail="task_id 无效")
    path = service.get_task_image_path(tid, image_path)
    if not path:
        raise HTTPException(status_code=404, detail="文件不存在")
    if variant == "thumb":
        thumb = get_or_create_thumbnail(path)
        if thumb:
            return build_immutable_file_response(
                path=thumb, filename=os.path.basename(thumb), media_type="image/webp"
            )
    # 文件名带微秒级时间戳,URL 即内容寻址,安全使用 immutable 强缓存。
    return build_immutable_file_response(path=path, filename=os.path.basename(path))
```

- [ ] **Step 4: 运行确认通过 + 全量回归**

Run: `pytest tests/routes/test_image_thumb_variant.py -v && pytest tests/ -x -q`
Expected: 全绿

- [ ] **Step 5: 提交**

```bash
git add app/routes/material.py app/routes/creation.py tests/routes/test_image_thumb_variant.py
git commit -m "feat(creation): 标准照槽位/产线结果图路由支持 variant=thumb 缩略图"
```

---

### Task 4: 前端 `thumbUrl()` 工具 + 列表/网格/卡片接入

**Files:**
- Create: `page/src/utils/imageUrl.ts`
- Modify: `page/src/pages/material/components/CharaList.tsx`(line ~96)
- Modify: `page/src/pages/material/components/CharaSidebar.tsx`(line ~62、~83)
- Modify: `page/src/pages/material/components/RawMaterialTab.tsx`(line ~237 hoverPreview、~242 网格)
- Modify: `page/src/pages/material/components/AvatarPickerModal.tsx`(line ~339 选图网格、~589 已选小预览;**不改** ~230 裁剪画布)
- Modify: `page/src/pages/material/components/PhotoTaskPage.tsx`(line ~660 参考图选择网格;**不改** ~247 候选图、~343 预览)
- Modify: `page/src/pages/material/components/OfficialContentTab.tsx`(line ~209)
- Modify: `page/src/pages/material/components/CharaProfilePage.tsx`(line ~465 同人立绘选择网格)
- Modify: `page/src/pages/home/components/BatchCreationPage.tsx`(line ~77)
- Modify: `page/src/pages/home/components/BatchTaskCard.tsx`(line ~172 头像、~266 缩略条、~373 网格)
- Modify: `page/src/pages/home/components/BatchTaskDetailModal.tsx`(line ~145)

**Interfaces:**
- Consumes: Task 2/3 的 `?variant=thumb` 查询参数。
- Produces: `thumbUrl(url: string | null | undefined): string`(`page/src/utils/imageUrl.ts` 导出)。

- [ ] **Step 1: 创建 `page/src/utils/imageUrl.ts`**

```ts
/**
 * 后端图片 URL 的缩略图变体。
 *
 * 列表/网格/卡片等小尺寸展示场景使用,后端返回 ~512px WebP(原图够小或生成失败时
 * 自动回退原图)。大图预览、裁剪、质检(feedback)场景必须继续用原始 URL。
 */
export function thumbUrl(url: string | null | undefined): string {
  if (!url) return "";
  // data:/blob: 本地资源、非本站 API 的 URL 原样返回
  if (!url.startsWith("/api/")) return url;
  return url.includes("?") ? `${url}&variant=thumb` : `${url}?variant=thumb`;
}
```

- [ ] **Step 2: 各组件接入**

每个文件:顶部加 `import { thumbUrl } from "@/utils/imageUrl";`,再把对应 `<img>` 的 `src={X}` 改为 `src={thumbUrl(X)}`。逐一列出(行号为当前近似值,以实际 grep 到的 `<img` 为准):

1. `CharaList.tsx` 角色列表头像:`src={thumbUrl(c.avatarUrl)}`
2. `CharaSidebar.tsx` 两处 24×24 头像(换头像按钮内 + 无按钮 fallback):`src={thumbUrl(chara.avatarUrl)}`
3. `RawMaterialTab.tsx` 参考图网格:`src={thumbUrl(im.url)}`;悬浮预览(240px):`src={thumbUrl(hoverPreview.url)}`
4. `AvatarPickerModal.tsx` 选图网格卡片(`ThumbCard`/映射项,约 line 339):`src={thumbUrl(url)}`;底部已选 36px 预览(约 line 589):`src={thumbUrl(selectedUrl)}`;**裁剪画布(约 line 230)保持 `src={imageUrl}` 不变**
5. `PhotoTaskPage.tsx` 参考图选择网格(约 line 660):`src={thumbUrl(img.url)}`;**候选图(~247)与预览(~343)不改**
6. `OfficialContentTab.tsx` 标准照槽位网格:`src={thumbUrl(url)}`
7. `CharaProfilePage.tsx` 同人立绘选择网格(约 line 465):`src={thumbUrl(img.url)}`
8. `BatchCreationPage.tsx` 角色选择 chip 头像:`src={thumbUrl(chara.avatarUrl)}`
9. `BatchTaskCard.tsx` 卡片头像(~172):`src={thumbUrl(task.charaAvatar)}`;结果图缩略条(~266)与展开网格(~373):`src={thumbUrl(img.url)}`;**`openLightbox(...)` 调用传的仍是原 `task.images`(内含原图 URL),不动**
10. `BatchTaskDetailModal.tsx` 头像(~145):`src={thumbUrl(task.charaAvatar)}`

**明确不改的文件**:`ImageFeedbackModal.tsx`(feedback 质检需原图看腿脚细节)、`repair/components/ImagePreviewModal.tsx`(大图预览)、`CreateCharaModal.tsx`(本地 blob 预览)。

- [ ] **Step 3: 静态检查**

Run: `cd page && npm run type-check && npm run lint`
Expected: 0 error(lint 允许既有 warning)

- [ ] **Step 4: 构建**

Run: `cd page && npm run build`
Expected: 构建成功,产物输出到 `../app/static/`

- [ ] **Step 5: 提交**

```bash
git add page/src/utils/imageUrl.ts page/src/pages app/static
git commit -m "feat(page): 列表/网格/卡片图片改用 variant=thumb 缩略图,大图预览与质检保持原图"
```

(若 repo 惯例是不提交 `app/static` 构建产物,则查看 `git log --oneline -- app/static` 确认;有历史提交记录才连带提交。)

---

### Task 5: 端到端验证(本地起服务实测)

**Files:** 无代码修改;验证 Task 1-4 的组合行为。

- [ ] **Step 1: 本地起后端**

Run(后台): `python -m uvicorn app.main:app --host 127.0.0.1 --port 8001`
Expected: 启动日志出现 `应用初始化完成`

- [ ] **Step 2: 用本地 data/ 里的真实大图验证缩略图链路**

本地 `data/material/characters/mchar_3695c70ca7`、`mchar_50c51e6e37` 有 1-2MB 的真实参考图。先查一个角色详情拿到 raw 图 URL,再分别请求原图与缩略图对比:

```bash
curl -s "http://127.0.0.1:8001/api/material/characters/mchar_3695c70ca7" | python -c "import json,sys; d=json.load(sys.stdin)['data']; print(d['raw_images'][0]['url'])"
# 用上一步输出的 URL(记为 $U):
curl -s -o /dev/null -w "original: %{size_download}B type=%{content_type}\n" "http://127.0.0.1:8001$U"
curl -s -o /dev/null -w "thumb:    %{size_download}B type=%{content_type} cache=%{header_json}\n" "http://127.0.0.1:8001$U?variant=thumb"
```

Expected: 原图 1-2MB / `image/png|jpeg`;缩略图 ≤100KB / `image/webp`;二次请求缩略图更快(磁盘已有 `.thumbs/*.webp`)。

- [ ] **Step 3: 验证前端构建产物引用**

浏览器打开 `http://127.0.0.1:8001/material`(生产构建由 FastAPI 静态托管),DevTools Network 过滤 `variant=thumb`:角色列表头像与参考图网格应请求缩略图;点开大图预览应请求无 `variant` 的原图 URL。若本机无浏览器,可用 curl 验证页面可达 + 抽查 `app/static` 产物中包含 `variant=thumb` 字符串:

```bash
grep -rl "variant=thumb" app/static/assets | head -3
```

Expected: 至少命中 1 个 js 产物文件。

- [ ] **Step 4: 停掉本地服务,汇报验证结果**

验证通过后向用户汇报:各页面图片负载对比(原图 vs 缩略图字节数)、建议部署到 118.196.73.79 后在真实带宽下体验。

---

## Self-Review

- **Spec 覆盖**:瓶颈是 4 类图片(raw 参考图、头像、标准照槽位、产线结果图)× 小尺寸展示场景 → Task 2/3 覆盖 4 条路由,Task 4 覆盖全部 13 处网格/列表/卡片 `<img>`;大图/裁剪/质检保持原图已写入 Global Constraints 与 Task 4 的"明确不改"清单。✓
- **占位符扫描**:无 TBD/TODO;Task 3 对 `CreationQuickCreateTask` 必填列给出了明确的处理指引(读模型补默认值)而非"适当处理"。✓
- **类型一致性**:`get_or_create_thumbnail(src_path: str) -> Optional[str]` 在 Task 1 定义、Task 2/3 消费;`thumbUrl(url: string | null | undefined): string` 在 Task 4 内定义并消费;`delete_thumbnail_for` 仅 Task 2 消费。✓
