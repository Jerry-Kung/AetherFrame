# tests/experiments/test_taxonomy.py
import os

import pytest

from experiments.casebank.taxonomy import Taxonomy, load_taxonomy

DATA = "experiments/cases/taxonomy.yaml"


def test_loads_real_taxonomy():
    tx = load_taxonomy(DATA)
    assert tx.version == "v2"
    assert "袜子" in tx.tags
    assert "上色感" in tx.tags["袜子"]
    # v2 新增（exp002 揭盲后用户确认）
    assert tx.is_valid("脚部/脚尖变色")
    assert tx.is_valid("袜子/穿鞋")
    assert tx.is_valid("画风/3D玩偶感")


def test_is_valid_accepts_known_child_tag():
    tx = load_taxonomy(DATA)
    assert tx.is_valid("袜子/上色感") is True
    assert tx.is_valid("脚部/夸张") is True


def test_is_valid_rejects_unknown_and_malformed():
    tx = load_taxonomy(DATA)
    assert tx.is_valid("袜子/不存在") is False
    assert tx.is_valid("不存在/上色感") is False
    assert tx.is_valid("袜子") is False          # 缺子类
    assert tx.is_valid("a/b/c") is False         # 层级过多


def test_normalize_passthrough_for_canonical_tag():
    tx = load_taxonomy(DATA)
    assert tx.normalize("袜子/上色感") == "袜子/上色感"


def test_normalize_resolves_alias_chain():
    tx = Taxonomy(
        version="v3",
        tags={"袜子": ["上色感"]},
        aliases={"丝袜/涂色": "袜子/上色", "袜子/上色": "袜子/上色感"},
    )
    assert tx.normalize("丝袜/涂色") == "袜子/上色感"


def test_normalize_raises_on_unknown():
    tx = load_taxonomy(DATA)
    with pytest.raises(ValueError):
        tx.normalize("袜子/查无此项")


def test_parent_of_returns_normalized_parent():
    tx = load_taxonomy(DATA)
    assert tx.parent_of("袜子/上色感") == "袜子"
