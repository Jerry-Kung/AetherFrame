"""feedback 标签配置：加载 / 归一化 / bad 推导 / 视图"""

import textwrap

from app.services.creation_service.feedback_tags import (
    DEFAULT_SEVERITY,
    SEVERITIES,
    derive_leg_foot_bad,
    get_tag_config,
    load_tag_config,
    normalize_selected_tags,
    tag_config_snapshot,
    tags_for_api,
)


def _write_config(tmp_path, content: str) -> str:
    p = tmp_path / "feedback_tags.yaml"
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return str(p)


SMALL_CONFIG = """
    version: 7
    tags:
      - { key: sock_wrinkle_heavy, label: 袜子皱褶过于夸张, polarity: negative, leg_foot_bad: true, taxonomy: 袜子/皱褶夸张, group: 袜子 }
      - { key: style_doll3d, label: 3D玩偶感, polarity: negative, leg_foot_bad: false, taxonomy: 画风/3D玩偶感, group: 画风 }
      - { key: pos_overall_good, label: 整体效果好, polarity: positive }
      - { key: neutral_normal, label: 正常, polarity: neutral }
"""


class TestLoad:
    def test_load_valid_config(self, tmp_path):
        cfg = load_tag_config(_write_config(tmp_path, SMALL_CONFIG))
        assert cfg["version"] == 7
        assert [t["key"] for t in cfg["tags"]] == [
            "sock_wrinkle_heavy", "style_doll3d", "pos_overall_good", "neutral_normal",
        ]
        neg = cfg["tags"][0]
        assert neg["polarity"] == "negative"
        assert neg["leg_foot_bad"] is True
        assert neg["taxonomy"] == "袜子/皱褶夸张"
        assert neg["group"] == "袜子"

    def test_load_missing_file_degrades_empty(self, tmp_path):
        cfg = load_tag_config(str(tmp_path / "nope.yaml"))
        assert cfg == {"version": 0, "tags": []}

    def test_load_broken_yaml_degrades_empty(self, tmp_path):
        cfg = load_tag_config(_write_config(tmp_path, "tags: [key: {{"))
        assert cfg == {"version": 0, "tags": []}

    def test_get_tag_config_reads_repo_file(self):
        get_tag_config.cache_clear()
        cfg = get_tag_config()
        keys = {t["key"] for t in cfg["tags"]}
        assert cfg["version"] >= 1
        assert {"sock_wrinkle_heavy", "leg_multi_missing", "sock_toe_separation",
                "pos_sock_style", "neutral_normal"} <= keys
        groups = [t["group"] for t in cfg["tags"] if t["polarity"] == "negative"]
        assert set(groups) == {"袜子", "脚部", "腿部与姿势", "画风", "脸部与身体"}
        assert groups[0] == "袜子"  # 生产最高优先级组最排最前

    def test_load_negative_missing_group_defaults_other(self, tmp_path):
        cfg = load_tag_config(_write_config(tmp_path, """
            version: 1
            tags:
              - { key: no_group_tag, label: 无分组, polarity: negative, leg_foot_bad: true, taxonomy: 其他/未分类 }
        """))
        assert cfg["tags"][0]["group"] == "其他"

    def test_load_positive_neutral_have_no_group(self, tmp_path):
        cfg = load_tag_config(_write_config(tmp_path, SMALL_CONFIG))
        assert "group" not in cfg["tags"][2]  # positive
        assert "group" not in cfg["tags"][3]  # neutral


class TestNormalize:
    def _cfg(self, tmp_path):
        return load_tag_config(_write_config(tmp_path, SMALL_CONFIG))

    def test_unknown_key_dropped(self, tmp_path):
        out = normalize_selected_tags(
            [{"key": "ghost_tag"}, {"key": "neutral_normal"}], self._cfg(tmp_path)
        )
        assert out == [{"key": "neutral_normal"}]

    def test_negative_missing_or_bad_severity_defaults_moderate(self, tmp_path):
        cfg = self._cfg(tmp_path)
        assert normalize_selected_tags([{"key": "sock_wrinkle_heavy"}], cfg) == [
            {"key": "sock_wrinkle_heavy", "severity": DEFAULT_SEVERITY}
        ]
        assert normalize_selected_tags(
            [{"key": "sock_wrinkle_heavy", "severity": "MAX"}], cfg
        ) == [{"key": "sock_wrinkle_heavy", "severity": "moderate"}]

    def test_negative_valid_severity_kept(self, tmp_path):
        cfg = self._cfg(tmp_path)
        for sev in SEVERITIES:
            out = normalize_selected_tags(
                [{"key": "sock_wrinkle_heavy", "severity": sev}], cfg
            )
            assert out == [{"key": "sock_wrinkle_heavy", "severity": sev}]

    def test_positive_and_neutral_strip_severity(self, tmp_path):
        out = normalize_selected_tags(
            [{"key": "pos_overall_good", "severity": "severe"}, {"key": "neutral_normal"}],
            self._cfg(tmp_path),
        )
        assert out == [{"key": "pos_overall_good"}, {"key": "neutral_normal"}]

    def test_dedup_keeps_first_and_none_input_ok(self, tmp_path):
        cfg = self._cfg(tmp_path)
        out = normalize_selected_tags(
            [{"key": "sock_wrinkle_heavy", "severity": "minor"},
             {"key": "sock_wrinkle_heavy", "severity": "severe"}],
            cfg,
        )
        assert out == [{"key": "sock_wrinkle_heavy", "severity": "minor"}]
        assert normalize_selected_tags(None, cfg) == []
        assert normalize_selected_tags([], cfg) == []


class TestDeriveBad:
    def _cfg(self, tmp_path):
        return load_tag_config(_write_config(tmp_path, SMALL_CONFIG))

    def test_legfoot_negative_tag_implies_bad(self, tmp_path):
        assert derive_leg_foot_bad(
            [{"key": "sock_wrinkle_heavy", "severity": "minor"}], self._cfg(tmp_path)
        ) is True

    def test_non_legfoot_negative_does_not_imply(self, tmp_path):
        assert derive_leg_foot_bad(
            [{"key": "style_doll3d", "severity": "severe"}], self._cfg(tmp_path)
        ) is False

    def test_no_tags_or_positive_only_is_false(self, tmp_path):
        cfg = self._cfg(tmp_path)
        assert derive_leg_foot_bad([], cfg) is False
        assert derive_leg_foot_bad([{"key": "pos_overall_good"}], cfg) is False


class TestViews:
    def test_tags_for_api_strips_taxonomy(self, tmp_path):
        cfg = load_tag_config(_write_config(tmp_path, SMALL_CONFIG))
        view = tags_for_api(cfg)
        assert view["version"] == 7
        assert view["tags"][0] == {
            "key": "sock_wrinkle_heavy", "label": "袜子皱褶过于夸张",
            "polarity": "negative", "leg_foot_bad": True, "group": "袜子",
        }
        assert view["tags"][2] == {
            "key": "pos_overall_good", "label": "整体效果好",
            "polarity": "positive", "leg_foot_bad": False, "group": None,
        }

    def test_snapshot_keeps_taxonomy_and_is_copy(self, tmp_path):
        cfg = load_tag_config(_write_config(tmp_path, SMALL_CONFIG))
        snap = tag_config_snapshot(cfg)
        assert snap["tags"][0]["taxonomy"] == "袜子/皱褶夸张"
        snap["tags"][0]["label"] = "篡改"
        assert cfg["tags"][0]["label"] == "袜子皱褶过于夸张"
