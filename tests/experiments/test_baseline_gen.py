import os

import experiments.baseline_gen as bg
from experiments.baseline_gen import run_baseline_gen

CFG = """
exp_id: exp001
benchmark: {bench}
variants: [baseline, slim]
images_per_cell: 3
concurrency: 10
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
    aspect_ratio: "16:9"
    text: 种子一
"""

ANCHORS = """
anchors:
  - anchor_id: a1
    question: q?
    ref_slot: face_close
"""


def _setup(tmp_path, monkeypatch):
    root = str(tmp_path)
    paths = {}
    for name, content in (("anchors.yaml", ANCHORS), ):
        p = os.path.join(root, name)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
        paths[name] = p
    bench_p = os.path.join(root, "bench.yaml")
    with open(bench_p, "w", encoding="utf-8") as f:
        f.write(BENCH.format(anchors=paths["anchors.yaml"].replace("\\", "/")))
    cfg_p = os.path.join(root, "exp.yaml")
    with open(cfg_p, "w", encoding="utf-8") as f:
        f.write(CFG.format(bench=bench_p.replace("\\", "/")))
    variants_root = os.path.join(root, "variants")
    monkeypatch.setattr(bg, "VARIANTS_ROOT", variants_root)
    monkeypatch.setattr(bg, "_load_profile", lambda cid: "角色档案全文")
    return cfg_p, variants_root


def test_baseline_gen_writes_and_freezes(tmp_path, monkeypatch):
    cfg_p, variants_root = _setup(tmp_path, monkeypatch)
    calls = []

    def fake_infer(prompt, **kw):
        calls.append(prompt)
        if len(calls) % 2 == 1:  # step1
            return "**[COMPOSITION_DECISION]**\naspect_ratio: 16:9\n\n模板正文"
        return "step2 最终 Prompt 全文"

    out = run_baseline_gen(cfg_p, infer=fake_infer)
    assert out["generated"] == ["s1"] and out["skipped"] == []
    target = os.path.join(variants_root, "exp001", "baseline", "s1.txt")
    with open(target, encoding="utf-8") as f:
        assert f.read() == "step2 最终 Prompt 全文"
    assert len(calls) == 2  # step1 + step2 各一次

    # 冻结语义：重复运行不覆盖、不再调 LLM
    out2 = run_baseline_gen(cfg_p, infer=fake_infer)
    assert out2 == {"generated": [], "skipped": ["s1"]}
    assert len(calls) == 2


def test_baseline_gen_only_filter(tmp_path, monkeypatch):
    cfg_p, _ = _setup(tmp_path, monkeypatch)
    out = run_baseline_gen(cfg_p, only=["nonexistent"],
                           infer=lambda *a, **k: "x")
    assert out == {"generated": [], "skipped": []}


def test_baseline_gen_rejects_empty_output(tmp_path, monkeypatch):
    import pytest
    cfg_p, variants_root = _setup(tmp_path, monkeypatch)
    with pytest.raises(RuntimeError, match="s1"):
        run_baseline_gen(cfg_p, infer=lambda *a, **k: "   ")
    target = os.path.join(variants_root, "exp001", "baseline", "s1.txt")
    assert not os.path.exists(target)
