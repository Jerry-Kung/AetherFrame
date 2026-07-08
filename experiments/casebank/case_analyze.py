"""大批量 Case 聚合分析：崩坏率按 变体/难度 交叉统计 + tag 频次（按 taxonomy 归一）。
Case 量增长后靠结构化 tags 保持准确；自由文本 feedback 不参与自动统计。"""
import argparse
import glob
import json
import os
import sys

from experiments.casebank.case_format import parse_cases
from experiments.casebank.taxonomy import load_taxonomy


def _rate(images, bad):
    return round(bad / images, 4) if images else None


def _group(cases):
    cells = len(cases)
    images = sum(c.images for c in cases)
    bad = sum(c.bad for c in cases)
    return {"cells": cells, "images": images, "bad": bad,
            "bad_rate": _rate(images, bad)}


def analyze(cases, taxonomy):
    by_variant_cases, by_dv, by_src = {}, {}, {}
    for c in cases:
        by_variant_cases.setdefault(c.variant, []).append(c)
        by_dv.setdefault(c.difficulty, {}).setdefault(c.variant, []).append(c)
        by_src.setdefault(c.source, []).append(c)

    by_variant = {v: _group(cs) for v, cs in by_variant_cases.items()}
    by_difficulty_variant = {
        diff: {v: _group(cs) for v, cs in variants.items()}
        for diff, variants in by_dv.items()
    }
    by_source = {s: _group(cs) for s, cs in by_src.items()}

    tag_freq, tag_freq_parent, unknown = {}, {}, []
    for c in cases:
        seen_norm = set()  # 归一化去重：同一 Case 内重复/别名同指的 tag 只计一次
        for tag in c.tags:
            try:
                norm = taxonomy.normalize(tag)
            except ValueError:
                unknown.append(tag)
                continue
            if norm in seen_norm:
                continue
            seen_norm.add(norm)
            parent = norm.split("/")[0]
            tag_freq.setdefault(c.variant, {})
            tag_freq[c.variant][norm] = tag_freq[c.variant].get(norm, 0) + 1
            tag_freq_parent.setdefault(c.variant, {})
            tag_freq_parent[c.variant][parent] = \
                tag_freq_parent[c.variant].get(parent, 0) + 1

    seen_unknown, unknown_deduped = set(), []
    for tag in unknown:
        if tag not in seen_unknown:
            seen_unknown.add(tag)
            unknown_deduped.append(tag)

    return {"by_variant": by_variant,
            "by_difficulty_variant": by_difficulty_variant,
            "by_source": by_source,
            "tag_freq": tag_freq, "tag_freq_parent": tag_freq_parent,
            "unknown_tags": unknown_deduped}


def load_cases_dir(dir_path):
    cases = []
    for p in sorted(glob.glob(os.path.join(dir_path, "*.txt"))):
        with open(p, "r", encoding="utf-8") as f:
            cases.extend(parse_cases(f.read()))
    return cases


def main():
    ap = argparse.ArgumentParser(description="Case 聚合分析")
    ap.add_argument("--cases-dir", required=True)
    ap.add_argument("--taxonomy", default="experiments/cases/taxonomy.yaml")
    args = ap.parse_args()
    cases = load_cases_dir(args.cases_dir)
    if not cases:
        print(f"[warn] 未在 {args.cases_dir} 下找到任何 Case（*.txt 为空或不存在）",
              file=sys.stderr)
    tx = load_taxonomy(args.taxonomy)
    print(json.dumps(analyze(cases, tx), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
