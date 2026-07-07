import os

from experiments.casebank.case_analyze import analyze, load_cases_dir
from experiments.casebank.case_format import Case, serialize_cases
from experiments.casebank.taxonomy import Taxonomy


def _tx():
    return Taxonomy(
        version="v2",
        tags={"袜子": ["上色感", "皱褶夸张"], "脚部": ["夸张"]},
        aliases={"丝袜/涂色感": "袜子/上色感"},
    )


def _case(variant, seed, difficulty, images, bad, tags):
    return Case(case_id=f"C_{variant}_{seed}", date="2026-07-07", source="exp002",
                character="castorice", seed_id=seed, difficulty=difficulty,
                variant=variant, images=images, bad=bad, tags=tags,
                taxonomy_version="v2", seed_prompt="s", final_prompt="f", feedback="")


def test_by_variant_bad_rate():
    cases = [_case("control", "s1", "hard", 5, 3, []),
             _case("control", "s2", "hard", 5, 2, []),
             _case("rulepack", "s1", "hard", 5, 1, []),
             _case("rulepack", "s2", "hard", 5, 0, [])]
    out = analyze(cases, _tx())
    assert out["by_variant"]["control"]["bad"] == 5
    assert out["by_variant"]["control"]["images"] == 10
    assert out["by_variant"]["control"]["bad_rate"] == 0.5
    assert out["by_variant"]["rulepack"]["bad_rate"] == 0.1


def test_by_difficulty_variant_split():
    cases = [_case("control", "s1", "hard", 4, 2, []),
             _case("control", "s2", "easy", 4, 0, [])]
    out = analyze(cases, _tx())
    assert out["by_difficulty_variant"]["hard"]["control"]["bad_rate"] == 0.5
    assert out["by_difficulty_variant"]["easy"]["control"]["bad_rate"] == 0.0


def test_tag_freq_normalized_child_and_parent():
    cases = [_case("control", "s1", "hard", 5, 3,
                   ["丝袜/涂色感", "袜子/皱褶夸张"]),      # 第一个走 alias 归一
             _case("control", "s2", "hard", 5, 1, ["袜子/上色感"])]
    out = analyze(cases, _tx())
    assert out["tag_freq"]["control"]["袜子/上色感"] == 2
    assert out["tag_freq"]["control"]["袜子/皱褶夸张"] == 1
    assert out["tag_freq_parent"]["control"]["袜子"] == 3   # 2+1 cell 计次


def test_unknown_tag_recorded_not_counted():
    cases = [_case("control", "s1", "hard", 5, 3, ["袜子/查无此项"])]
    out = analyze(cases, _tx())
    assert "袜子/查无此项" in out["unknown_tags"]
    assert out["tag_freq"].get("control", {}) == {}


def test_zero_images_bad_rate_none():
    cases = [_case("control", "s1", "hard", 0, 0, [])]
    out = analyze(cases, _tx())
    assert out["by_variant"]["control"]["bad_rate"] is None


def test_by_source_group():
    c1 = _case("control", "s1", "hard", 5, 2, [])
    c2 = _case("control", "s2", "hard", 5, 1, [])
    c2.source = "production"
    out = analyze([c1, c2], _tx())
    assert out["by_source"]["exp002"]["bad_rate"] == 0.4
    assert out["by_source"]["production"]["bad_rate"] == 0.2


def test_load_cases_dir_merges_files(tmp_path):
    d = str(tmp_path)
    with open(os.path.join(d, "a.txt"), "w", encoding="utf-8") as f:
        f.write(serialize_cases([_case("control", "s1", "hard", 5, 1, [])]))
    with open(os.path.join(d, "b.txt"), "w", encoding="utf-8") as f:
        f.write(serialize_cases([_case("rulepack", "s1", "hard", 5, 0, [])]))
    cases = load_cases_dir(d)
    assert {c.variant for c in cases} == {"control", "rulepack"}
