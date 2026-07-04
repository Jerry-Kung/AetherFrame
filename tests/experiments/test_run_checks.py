import json
import os

from experiments.checker.run_checks import run_all_checks
from experiments.layout import ExpLayout

CFG = """
exp_id: exp001
benchmark: {bench}
variants: [baseline, slim]
images_per_cell: 1
concurrency: 2
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
  - anchor_id: crown
    question: 是否佩戴相同的花冠？
    ref_slot: face_close
"""


def _setup(tmp_path):
    root = str(tmp_path)
    anchors_p = os.path.join(root, "anchors.yaml")
    bench_p = os.path.join(root, "bench.yaml")
    cfg_p = os.path.join(root, "exp.yaml")
    with open(anchors_p, "w", encoding="utf-8") as f:
        f.write(ANCHORS)
    with open(bench_p, "w", encoding="utf-8") as f:
        f.write(BENCH.format(anchors=anchors_p.replace("\\", "/")))
    with open(cfg_p, "w", encoding="utf-8") as f:
        f.write(CFG.format(bench=bench_p.replace("\\", "/")))
    results_root = os.path.join(root, "results")
    lay = ExpLayout(results_root, "exp001")
    entries = []
    for variant in ("baseline", "slim"):
        img = lay.image_path(variant, "s1", 1)
        os.makedirs(os.path.dirname(img), exist_ok=True)
        with open(img, "wb") as f:
            f.write(b"fake-png")
        entries.append({
            "variant": variant, "seed_id": "s1", "image_index": 1,
            "character_id": "mchar_x",
            "image_path": os.path.relpath(img, lay.root).replace("\\", "/"),
            "aspect_ratio": "16:9", "ok": True,
        })
    os.makedirs(os.path.dirname(lay.manifest_path()), exist_ok=True)
    with open(lay.manifest_path(), "w", encoding="utf-8") as f:
        json.dump({"entries": entries}, f)
    return cfg_p, results_root, lay


def _fake_infer(prompt, image_path=None, **kw):
    if "几条腿" in prompt:
        return "2"
    if "花冠" in prompt:
        return "是"
    return "否，正常。"


def test_run_all_checks_writes_json(tmp_path, monkeypatch):
    import experiments.checker.checks as checks_mod
    monkeypatch.setattr(checks_mod, "_resolve_ref_slot_path",
                        lambda cid, slot: __file__)
    cfg_p, results_root, lay = _setup(tmp_path)
    stats = run_all_checks(cfg_p, results_root=results_root, infer=_fake_infer)
    assert stats == {"checked": 2, "skipped": 0, "failed": 0}
    with open(lay.check_path("slim", "s1", 1), encoding="utf-8") as f:
        doc = json.load(f)
    assert doc["structure"]["leg_count"]["pass"] is True
    assert doc["anchors"]["crown"]["answer"] == "yes"
    assert doc["character_id"] == "mchar_x"


def test_run_all_checks_skips_existing(tmp_path, monkeypatch):
    import experiments.checker.checks as checks_mod
    monkeypatch.setattr(checks_mod, "_resolve_ref_slot_path",
                        lambda cid, slot: __file__)
    cfg_p, results_root, lay = _setup(tmp_path)
    run_all_checks(cfg_p, results_root=results_root, infer=_fake_infer)
    stats2 = run_all_checks(cfg_p, results_root=results_root, infer=_fake_infer)
    assert stats2 == {"checked": 0, "skipped": 2, "failed": 0}
    stats3 = run_all_checks(cfg_p, results_root=results_root, force=True,
                            infer=_fake_infer)
    assert stats3["checked"] == 2
