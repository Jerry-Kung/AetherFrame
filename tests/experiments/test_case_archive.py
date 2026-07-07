import json
import os

import pytest

from experiments.casebank.case_archive import archive_experiment, build_cases
from experiments.casebank.case_format import parse_cases
from experiments.config import load_benchmark
from experiments.layout import ExpLayout

BENCH = """
characters:
  castorice:
    character_id: mchar_x
    anchors: {anchors}
seeds:
  - {{seed_id: s_easy, character: castorice, difficulty: easy, aspect_ratio: "3:4", text: 种子E}}
  - {{seed_id: s_hard, character: castorice, difficulty: hard, aspect_ratio: "4:3", text: 种子H}}
"""
ANCHORS = "anchors:\n  - {anchor_id: a1, question: q?, ref_slot: face_close}\n"


def _setup(tmp_path):
    root = str(tmp_path)
    anchors_p = os.path.join(root, "anchors.yaml")
    with open(anchors_p, "w", encoding="utf-8") as f:
        f.write(ANCHORS)
    bench_p = os.path.join(root, "bench.yaml")
    with open(bench_p, "w", encoding="utf-8") as f:
        f.write(BENCH.format(anchors=anchors_p.replace("\\", "/")))
    layout = ExpLayout(os.path.join(root, "results"), "exp002")
    # 两变体 × 两种子，每格 2 张
    entries = []
    for variant in ("control", "rulepack"):
        for seed in ("s_easy", "s_hard"):
            pdir = layout.prompts_dir(variant)
            os.makedirs(pdir, exist_ok=True)
            with open(layout.prompt_path(variant, seed), "w", encoding="utf-8") as f:
                f.write(f"{variant}/{seed} 正文\n**Negative Prompt**：穿鞋。")
            for k in (1, 2):
                entries.append({"variant": variant, "seed_id": seed,
                                "image_index": k, "character_id": "mchar_x",
                                "image_path": f"images/{variant}/{seed}/img_{k}.png",
                                "aspect_ratio": "3:4", "ok": True})
    os.makedirs(layout.root, exist_ok=True)
    with open(layout.manifest_path(), "w", encoding="utf-8") as f:
        json.dump({"entries": entries}, f)
    return layout, bench_p


def test_build_cases_one_per_variant_seed_cell(tmp_path):
    layout, bench_p = _setup(tmp_path)
    bench = load_benchmark(bench_p)
    cases = build_cases(layout, bench, source="exp002", date="2026-07-07")
    assert len(cases) == 4          # 2 变体 × 2 种子
    cell = {(c.variant, c.seed_id) for c in cases}
    assert cell == {("control", "s_easy"), ("control", "s_hard"),
                    ("rulepack", "s_easy"), ("rulepack", "s_hard")}


def test_build_cases_fills_meta_and_prompts(tmp_path):
    layout, bench_p = _setup(tmp_path)
    bench = load_benchmark(bench_p)
    cases = build_cases(layout, bench, source="exp002", date="2026-07-07")
    hard = next(c for c in cases if c.variant == "control" and c.seed_id == "s_hard")
    assert hard.images == 2
    assert hard.bad == 0                    # 无 ratings
    assert hard.difficulty == "hard"
    assert hard.seed_prompt == "种子H"
    assert "control/s_hard 正文" in hard.final_prompt
    assert hard.tags == []
    assert hard.feedback == ""


def test_build_cases_counts_bad_from_ratings_and_joins_notes(tmp_path):
    layout, bench_p = _setup(tmp_path)
    bench = load_benchmark(bench_p)
    key = {"R001": {"variant": "rulepack", "seed_id": "s_easy", "image_index": 1},
           "R002": {"variant": "rulepack", "seed_id": "s_easy", "image_index": 2}}
    ratings = {"R001": {"leg": "broken", "note": "袜子上色感"},
               "R002": {"leg": "ok", "note": ""}}
    cases = build_cases(layout, bench, source="exp002", date="2026-07-07",
                        ratings=ratings, key=key)
    cell = next(c for c in cases if c.variant == "rulepack" and c.seed_id == "s_easy")
    assert cell.bad == 1
    assert "袜子上色感" in cell.feedback


def test_build_cases_all_images_failed_still_produces_case_with_zero_images(tmp_path):
    layout, bench_p = _setup(tmp_path)
    bench = load_benchmark(bench_p)
    with open(layout.manifest_path(), encoding="utf-8") as f:
        manifest = json.load(f)
    for e in manifest["entries"]:
        if e["variant"] == "control" and e["seed_id"] == "s_easy":
            e["ok"] = False
    with open(layout.manifest_path(), "w", encoding="utf-8") as f:
        json.dump(manifest, f)
    cases = build_cases(layout, bench, source="exp002", date="2026-07-07")
    assert len(cases) == 4          # 全格失败的格子也要产出 Case，不能静默丢弃
    cell = next(c for c in cases if c.variant == "control" and c.seed_id == "s_easy")
    assert cell.images == 0
    assert cell.bad == 0


def test_build_cases_raises_on_unknown_seed_id(tmp_path):
    layout, bench_p = _setup(tmp_path)
    bench = load_benchmark(bench_p)
    with open(layout.manifest_path(), encoding="utf-8") as f:
        manifest = json.load(f)
    manifest["entries"].append({
        "variant": "control", "seed_id": "s_unknown", "image_index": 1,
        "character_id": "mchar_x",
        "image_path": "images/control/s_unknown/img_1.png",
        "aspect_ratio": "3:4", "ok": True,
    })
    with open(layout.manifest_path(), "w", encoding="utf-8") as f:
        json.dump(manifest, f)
    with pytest.raises(ValueError, match="s_unknown"):
        build_cases(layout, bench, source="exp002", date="2026-07-07")


def test_archive_experiment_writes_parseable_file(tmp_path):
    layout, bench_p = _setup(tmp_path)
    bench = load_benchmark(bench_p)
    out = os.path.join(str(tmp_path), "exp002_cases.txt")
    path = archive_experiment(layout, bench, source="exp002", out_path=out,
                              date="2026-07-07")
    assert os.path.isfile(path)
    with open(path, encoding="utf-8") as f:
        cases = parse_cases(f.read())
    assert len(cases) == 4
