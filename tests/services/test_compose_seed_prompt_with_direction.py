import uuid

import pytest

from app.models.material import MaterialCreativeDirection, MaterialCharacter
from app.schemas.creation import SeedPayload
from app.services.creation_service.prompt_precreation_service import (
    compose_seed_prompt_with_direction,
)


def _make_character(db_session) -> MaterialCharacter:
    char_id = f"mchar_{uuid.uuid4().hex[:10]}"
    row = MaterialCharacter(
        id=char_id,
        name="Test",
        display_name="Test",
        status="idle",
        setting_text="",
    )
    db_session.add(row)
    db_session.commit()
    return row


def test_no_direction_returns_plain_text(db_session):
    out = compose_seed_prompt_with_direction(
        SeedPayload(text="seed", creative_direction_id=None),
        db_session,
    )
    assert out == "seed"
    assert "### 创作创意方向" not in out


def test_str_input_via_from_raw(db_session):
    out = compose_seed_prompt_with_direction("seed text", db_session)
    assert out == "seed text"


def test_dict_input_via_from_raw(db_session):
    char = _make_character(db_session)
    dir_id = str(uuid.uuid4())
    db_session.add(
        MaterialCreativeDirection(
            id=dir_id,
            character_id=char.id,
            title="主题A",
            description="## 核心主题\n描述",
            divergence="low",
        )
    )
    db_session.commit()
    out = compose_seed_prompt_with_direction(
        {"text": "x", "creative_direction_id": dir_id},
        db_session,
    )
    assert "### 创作创意方向" in out
    assert "主题A" in out


def test_with_direction_composes_markdown(db_session):
    char = _make_character(db_session)
    dir_id = str(uuid.uuid4())
    db_session.add(
        MaterialCreativeDirection(
            id=dir_id,
            character_id=char.id,
            title="标题行",
            description="描述正文",
            divergence="mid",
        )
    )
    db_session.commit()
    out = compose_seed_prompt_with_direction(
        SeedPayload(text="种子句", creative_direction_id=dir_id),
        db_session,
    )
    expected = (
        "### 创作创意方向\n"
        "标题行\n"
        "\n"
        "描述正文\n"
        "\n"
        "### 初始创作种子\n"
        "种子句"
    )
    assert out == expected


def test_invalid_direction_id_falls_back(db_session, caplog):
    out = compose_seed_prompt_with_direction(
        SeedPayload(text="plain", creative_direction_id="missing-id"),
        db_session,
    )
    assert out == "plain"
    assert any("compose: direction" in r.message for r in caplog.records)


def test_markdown_blank_line_format(db_session):
    char = _make_character(db_session)
    dir_id = str(uuid.uuid4())
    db_session.add(
        MaterialCreativeDirection(
            id=dir_id,
            character_id=char.id,
            title="T",
            description="D",
            divergence="high",
        )
    )
    db_session.commit()
    out = compose_seed_prompt_with_direction(
        SeedPayload(text="S", creative_direction_id=dir_id),
        db_session,
    )
    parts = out.split("\n")
    assert parts[0] == "### 创作创意方向"
    assert parts[1] == "T"
    assert parts[2] == ""
    assert parts[3] == "D"
    assert parts[4] == ""
    assert parts[5] == "### 初始创作种子"
    assert parts[6] == "S"


def test_description_not_stripped(db_session):
    char = _make_character(db_session)
    dir_id = str(uuid.uuid4())
    trailing = "尾段\n\n"
    db_session.add(
        MaterialCreativeDirection(
            id=dir_id,
            character_id=char.id,
            title="T",
            description=f"正文{trailing}",
            divergence="low",
        )
    )
    db_session.commit()
    out = compose_seed_prompt_with_direction(
        SeedPayload(text="s", creative_direction_id=dir_id),
        db_session,
    )
    assert f"正文{trailing}" in out
    assert out.endswith("s")
