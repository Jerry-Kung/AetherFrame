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
