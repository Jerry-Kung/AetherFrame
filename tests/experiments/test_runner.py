import json
import os

import experiments.runner as rn
from experiments.layout import ExpLayout
from experiments.runner import run_experiment

CFG = """
exp_id: exp001
benchmark: {bench}
variants: [baseline, slim]
images_per_cell: 2
concurrency: 3
review_shuffle_seed: 1
"""

BENCH = """
characters:
  castorice:
    character_id: mchar_x
    anchors: {anchors}
seeds:
  - seed_id: s1
    character: castorice
    difficulty: easy
    aspect_ratio: "4:3"
    text: 种子一
"""

ANCHORS = "anchors:\n  - {anchor_id: a1, question: q?, ref_slot: face_close}\n"


def _setup(tmp_path, monkeypatch):
    root = str(tmp_path)
    anchors_p = os.path.join(root, "anchors.yaml")
    with open(anchors_p, "w", encoding="utf-8") as f:
        f.write(ANCHORS)
    bench_p = os.path.join(root, "bench.yaml")
    with open(bench_p, "w", encoding="utf-8") as f:
        f.write(BENCH.format(anchors=anchors_p.replace("\\", "/")))
    cfg_p = os.path.join(root, "exp.yaml")
    with open(cfg_p, "w", encoding="utf-8") as f:
        f.write(CFG.format(bench=bench_p.replace("\\", "/")))
    variants_root = os.path.join(root, "variants")
    for variant in ("baseline", "slim"):
        d = os.path.join(variants_root, "exp001", variant)
        os.makedirs(d)
        with open(os.path.join(d, "s1.txt"), "w", encoding="utf-8") as f:
            f.write(f"{variant} 的 Prompt 全文")
    monkeypatch.setattr(rn, "VARIANTS_ROOT", variants_root)
    monkeypatch.setattr(rn, "_resolve_refs", lambda cid: ["r1.png", "r2.png"])
    return cfg_p, os.path.join(root, "results")


def test_run_experiment_generates_all_cells(tmp_path, monkeypatch):
    cfg_p, results_root = _setup(tmp_path, monkeypatch)
    calls = []

    def fake_gen(Content, output_path, file_name, aspect_ratio="16:9", **kw):
        calls.append((Content[0]["text"], aspect_ratio))
        os.makedirs(output_path, exist_ok=True)
        with open(os.path.join(output_path, file_name), "wb") as f:
            f.write(b"png")
        return True

    stats = run_experiment(cfg_p, results_root=results_root, gen_image=fake_gen)
    assert stats == {"generated": 4, "skipped": 0, "failed": 0}  # 2 variants × 1 seed × 2 张
    assert all(ar == "4:3" for _, ar in calls)                   # 画幅取 benchmark
    texts = {t for t, _ in calls}
    assert texts == {"baseline 的 Prompt 全文", "slim 的 Prompt 全文"}

    lay = ExpLayout(results_root, "exp001")
    with open(lay.manifest_path(), encoding="utf-8") as f:
        entries = json.load(f)["entries"]
    assert len(entries) == 4
    assert {e["variant"] for e in entries} == {"baseline", "slim"}
    assert all(e["ok"] for e in entries)
    assert all("\\" not in e["image_path"] for e in entries)
    # 发送全文存档
    with open(lay.prompt_path("slim", "s1"), encoding="utf-8") as f:
        assert f.read() == "slim 的 Prompt 全文"


def test_run_experiment_resumes(tmp_path, monkeypatch):
    cfg_p, results_root = _setup(tmp_path, monkeypatch)
    n_calls = {"n": 0}

    def fake_gen(Content, output_path, file_name, **kw):
        n_calls["n"] += 1
        os.makedirs(output_path, exist_ok=True)
        with open(os.path.join(output_path, file_name), "wb") as f:
            f.write(b"png")
        return True

    run_experiment(cfg_p, results_root=results_root, gen_image=fake_gen)
    stats2 = run_experiment(cfg_p, results_root=results_root, gen_image=fake_gen)
    assert stats2 == {"generated": 0, "skipped": 4, "failed": 0}
    assert n_calls["n"] == 4  # 第二轮零调用


def test_run_experiment_records_failure(tmp_path, monkeypatch):
    cfg_p, results_root = _setup(tmp_path, monkeypatch)
    stats = run_experiment(cfg_p, results_root=results_root,
                           gen_image=lambda **kw: False)
    assert stats["failed"] == 4 and stats["generated"] == 0


def test_save_manifest_leaves_no_tmp(tmp_path, monkeypatch):
    cfg_p, results_root = _setup(tmp_path, monkeypatch)

    def fake_gen(Content, output_path, file_name, **kw):
        os.makedirs(output_path, exist_ok=True)
        with open(os.path.join(output_path, file_name), "wb") as f:
            f.write(b"png")
        return True

    run_experiment(cfg_p, results_root=results_root, gen_image=fake_gen)
    lay = ExpLayout(results_root, "exp001")
    assert os.path.isfile(lay.manifest_path())
    assert not os.path.exists(lay.manifest_path() + ".tmp")
