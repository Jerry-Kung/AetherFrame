from sqlalchemy import text

from app.models.material import MaterialCharacter, MaterialCreativeDirection


def test_home_settings_column_exists_and_defaults_to_null(db_session):
    """home_settings 列必须存在,且新建方向默认为 NULL。"""
    cols = db_session.execute(
        text("PRAGMA table_info(material_creative_directions)")
    ).fetchall()
    names = {c[1] for c in cols}
    assert "home_settings" in names, f"missing home_settings column, got: {sorted(names)}"

    parent = MaterialCharacter(
        id="chr_dummy_hs",
        name="Dummy",
        display_name="Dummy",
        status="idle",
        setting_text="",
    )
    db_session.add(parent)
    db_session.commit()

    row = MaterialCreativeDirection(
        id="cd_test_home_settings_null",
        character_id="chr_dummy_hs",
        title="t",
        description="d",
        divergence="mid",
    )
    db_session.add(row)
    db_session.commit()
    reloaded = db_session.get(MaterialCreativeDirection, "cd_test_home_settings_null")
    assert reloaded.home_settings is None


import json
from app.services.material_service.creative_direction_generation_service import (
    _parse_direction_json,
)


def test_parse_direction_json_extracts_home_settings():
    raw = json.dumps({
        "title": "T",
        "description": "D",
        "home_settings": ["卧室大床", "客厅沙发", "飘窗台"],
    })
    title, desc, home = _parse_direction_json(raw)
    assert title == "T"
    assert desc == "D"
    assert home == ["卧室大床", "客厅沙发", "飘窗台"]


def test_parse_direction_json_missing_home_settings_is_none():
    raw = json.dumps({"title": "T", "description": "D"})
    _, _, home = _parse_direction_json(raw)
    assert home is None


def test_parse_direction_json_trims_and_dedups_home_settings():
    raw = json.dumps({
        "title": "T",
        "description": "D",
        "home_settings": [" 卧室大床 ", "卧室大床", "客厅沙发", "", None, 123],
    })
    _, _, home = _parse_direction_json(raw)
    assert home == ["卧室大床", "客厅沙发"]
