"""MATERIAL_CHARACTERS_DIR 环境变量覆盖：实验时把角色根目录切到生产拷贝，默认行为不变。"""
import os

from app.services import directory_service as ds


def test_default_characters_dir_unchanged(monkeypatch):
    monkeypatch.delenv("MATERIAL_CHARACTERS_DIR", raising=False)
    assert ds.get_material_characters_dir() == os.path.join(
        ds.get_material_dir(), "characters"
    )


def test_env_override_wins(monkeypatch, tmp_path):
    override = str(tmp_path / "characters_production" / "characters")
    monkeypatch.setenv("MATERIAL_CHARACTERS_DIR", override)
    assert ds.get_material_characters_dir() == os.path.abspath(override)


def test_empty_env_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("MATERIAL_CHARACTERS_DIR", "")
    assert ds.get_material_characters_dir() == os.path.join(
        ds.get_material_dir(), "characters"
    )
