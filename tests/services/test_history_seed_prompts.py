from app.services.material_service.history_seed_prompts import build_history_seed_prompts


def test_empty_returns_placeholder():
    assert build_history_seed_prompts({}) == "（暂无历史种子提示词）"
    assert build_history_seed_prompts({"official_seed_prompts": None}) == "（暂无历史种子提示词）"


def test_no_direction_includes_null_dir_and_all_general():
    bio = {
        "official_seed_prompts": {
            "character_specific": [
                {"text": "null-dir", "creative_direction_id": None},
                {"text": "d1", "creative_direction_id": "D1"},
                {"text": "d2", "creative_direction_id": "D2"},
            ],
            "general": [{"text": "g1"}, {"text": "g2"}],
        }
    }
    result = build_history_seed_prompts(bio, creative_direction_id=None)
    lines = result.split("\n")
    assert len(lines) == 3
    assert "null-dir" in result
    assert "g1" in result
    assert "g2" in result
    assert "d1" not in result
    assert "d2" not in result


def test_with_direction_only_same_dir():
    bio = {
        "official_seed_prompts": {
            "character_specific": [
                {"text": "d1a", "creative_direction_id": "D1"},
                {"text": "d2a", "creative_direction_id": "D2"},
                {"text": "d2b", "creative_direction_id": "D2"},
            ],
            "general": [{"text": "legacy"}],
        }
    }
    result = build_history_seed_prompts(bio, creative_direction_id="D2")
    lines = result.split("\n")
    assert len(lines) == 2
    assert "d2a" in result
    assert "d2b" in result
    assert "d1a" not in result
    assert "legacy" not in result


def test_legacy_cs_without_dir_field_treated_as_null():
    bio = {
        "official_seed_prompts": {
            "character_specific": [{"text": "old-entry"}],
            "general": [],
        }
    }
    result = build_history_seed_prompts(bio, creative_direction_id=None)
    assert "old-entry" in result


def test_fixed_unused_texts_backward_compat():
    bio = {"official_seed_prompts": {"character_specific": [], "general": []}}
    result = build_history_seed_prompts(bio, fixed_unused_texts=["extra1", "extra2"])
    assert "extra1" in result
    assert "extra2" in result
