"""实验报告：自动指标聚合（本文件 Task 10 部分）+ 盲评页与合流报告（Task 11 追加）。"""
import glob
import json
import os

from experiments.layout import ExpLayout

_RATE_KEYS = {
    "leg_count": "multi_leg_rate",
    "torso_dup": "torso_dup_rate",
    "neck_waist_twist": "neck_waist_twist_rate",
    "furniture_broken": "furniture_broken_rate",
}


def _load_check_docs(layout: ExpLayout) -> list:
    docs = []
    pattern = os.path.join(layout.root, "checks", "*.json")
    for p in sorted(glob.glob(pattern)):
        with open(p, "r", encoding="utf-8") as f:
            docs.append(json.load(f))
    return docs


def _variant_metrics(docs: list) -> dict:
    out = {"images": len(docs), "unparsed": {}}
    for check_id, rate_key in _RATE_KEYS.items():
        parsed = fail = unparsed = 0
        for d in docs:
            item = d.get("structure", {}).get(check_id, {})
            p = item.get("pass")
            if "error" in item or p is None:
                unparsed += 1
            else:
                parsed += 1
                if p is False:
                    fail += 1
        out[rate_key] = round(fail / parsed, 4) if parsed else None
        out["unparsed"][check_id] = unparsed
    yes = judged = 0
    for d in docs:
        for a in d.get("anchors", {}).values():
            ans = a.get("answer")
            if ans in ("yes", "no"):
                judged += 1
                if ans == "yes":
                    yes += 1
    out["anchor_retention_rate"] = round(yes / judged, 4) if judged else None
    return out


def aggregate_metrics(layout: ExpLayout) -> dict:
    docs = _load_check_docs(layout)
    by_variant_docs, by_seed_docs = {}, {}
    for d in docs:
        by_variant_docs.setdefault(d["variant"], []).append(d)
        by_seed_docs.setdefault(d["seed_id"], {}).setdefault(
            d["variant"], []).append(d)

    by_variant = {v: _variant_metrics(ds) for v, ds in by_variant_docs.items()}
    delta_pp = {}
    base, slim = by_variant.get("baseline"), by_variant.get("slim")
    if base and slim:
        for key in list(_RATE_KEYS.values()) + ["anchor_retention_rate"]:
            b, s = base.get(key), slim.get(key)
            delta_pp[key] = (round((s - b) * 100, 1)
                             if b is not None and s is not None else None)
    by_seed = {
        seed_id: {v: _variant_metrics(ds) for v, ds in variants.items()}
        for seed_id, variants in by_seed_docs.items()
    }
    return {"by_variant": by_variant, "delta_pp": delta_pp, "by_seed": by_seed}


def write_metrics(layout: ExpLayout) -> dict:
    metrics = aggregate_metrics(layout)
    with open(layout.metrics_path(), "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
    return metrics
