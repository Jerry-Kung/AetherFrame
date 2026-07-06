import importlib
import os

import pytest

import app.config as config_module


def test_config_defaults():
    importlib.reload(config_module)
    assert config_module.MATERIAL_CREATIVE_DIRECTION_PER_CHARACTER_LIMIT == 20
    assert config_module.MATERIAL_TASK_PER_CHARACTER_LIMIT == 2
    assert config_module.MATERIAL_LLM_GLOBAL_CONCURRENCY == 4
    assert config_module.MATERIAL_TASK_RETENTION_DAYS == 30
    assert config_module.MATERIAL_CREATIVE_DIRECTION_INITIAL_INPUT_MAX == 500


def test_config_env_override(monkeypatch):
    monkeypatch.setenv("MATERIAL_CREATIVE_DIRECTION_PER_CHARACTER_LIMIT", "15")
    monkeypatch.setenv("MATERIAL_LLM_GLOBAL_CONCURRENCY", "8")
    importlib.reload(config_module)
    assert config_module.MATERIAL_CREATIVE_DIRECTION_PER_CHARACTER_LIMIT == 15
    assert config_module.MATERIAL_LLM_GLOBAL_CONCURRENCY == 8


def test_config_env_invalid_falls_back(monkeypatch):
    monkeypatch.setenv("MATERIAL_TASK_PER_CHARACTER_LIMIT", "abc")
    importlib.reload(config_module)
    assert config_module.MATERIAL_TASK_PER_CHARACTER_LIMIT == 2
