import json
import os

from experiments.layout import ExpLayout
from experiments.report import aggregate_metrics


def _check_doc(variant, seed_id, k, leg_pass, anchors_yes, anchors_total):
    anchors = {}
    for i in range(anchors_total):
        anchors[f"a{i}"] = {"answer": "yes" if i < anchors_yes else "no",
                            "raw": ""}
    return {
        "variant": variant, "seed_id": seed_id, "image_index": k,
        "image_path": f"images/{variant}/{seed_id}/img_{k}.png",
        "character_id": "mchar_x",
        "structure": {
            "leg_count": {"kind": "count", "value": 2 if leg_pass else 4,
                          "pass": leg_pass, "raw": ""},
            "torso_dup": {"kind": "yes_no", "verdict": "no", "reason": "",
                          "pass": True, "raw": ""},
            "neck_waist_twist": {"kind": "yes_no", "verdict": "no",
                                 "reason": "", "pass": True, "raw": ""},
            "furniture_broken": {"kind": "yes_no", "verdict": None,
                                 "reason": "", "pass": None, "raw": ""},
        },
        "anchors": anchors,
    }


def _setup(tmp_path):
    lay = ExpLayout(str(tmp_path), "exp001")
    docs = [
        _check_doc("baseline", "s1", 1, False, 2, 4),  # 多腿；锚点 2/4
        _check_doc("baseline", "s1", 2, True, 4, 4),
        _check_doc("slim", "s1", 1, True, 4, 4),
        _check_doc("slim", "s1", 2, True, 3, 4),
    ]
    for d in docs:
        p = lay.check_path(d["variant"], d["seed_id"], d["image_index"])
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(d, f)
    return lay


def test_aggregate_metrics(tmp_path):
    lay = _setup(tmp_path)
    m = aggregate_metrics(lay)
    base = m["by_variant"]["baseline"]
    slim = m["by_variant"]["slim"]
    assert base["images"] == 2 and slim["images"] == 2
    assert base["multi_leg_rate"] == 0.5          # 1/2
    assert slim["multi_leg_rate"] == 0.0
    assert base["anchor_retention_rate"] == 0.75  # (2+4)/8
    assert slim["anchor_retention_rate"] == 0.875 # (4+3)/8
    # furniture_broken 全部 pass=None → 分母 0，rate 为 None，unparsed=2
    assert base["furniture_broken_rate"] is None
    assert base["unparsed"]["furniture_broken"] == 2
    assert m["delta_pp"]["multi_leg_rate"] == -50.0
    assert m["delta_pp"]["anchor_retention_rate"] == 12.5
    assert "s1" in m["by_seed"]
