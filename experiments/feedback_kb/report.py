"""带证据的分析报告（设计文档 §9）：排行榜 + Top-K 关联证据 → JSON + Markdown。
全确定性；趋势只入紧迫度公式与行内展示，不单列章节（B 本轮只算不展示）。"""
import argparse
import json
import os
from datetime import datetime

from experiments.feedback_kb.correlate import (FEATURE_DIMS, N_MIN,
                                               correlate_top_modes)
from experiments.feedback_kb.kb_query import load_kb, load_tag_taxonomy_map
from experiments.feedback_kb.rank import rank_modes
from experiments.feedback_kb.versions import load_versions

TOP_K = 5

_CONF_LABEL = {"strong": "★强", "weak": "△弱", "insufficient": "×证据不足"}


def build_report(kb: list, timeline, top_k: int = TOP_K) -> dict:
    tag_map = load_tag_taxonomy_map()
    ranking = rank_modes(kb, timeline, tag_map)
    top_modes = [r["mode"] for r in ranking[:top_k]]
    corr = correlate_top_modes(kb, top_modes, tag_map)
    pose_pending = sum(1 for c in kb if not c.get("pose_family"))
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "kb_cases": len(kb),
        "pose_pending": pose_pending,
        "n_min": N_MIN,
        "top_k": top_k,
        "feature_dims": list(FEATURE_DIMS),
        "tested_combinations": corr["tested_combinations"],
        "ranking": ranking,
        "correlations": corr["findings"],
    }


def render_markdown(report: dict) -> str:
    lines = [
        "# 生产 Feedback 分析报告（知识库驱动）",
        "",
        f"- 生成时间：{report['generated_at']}",
        f"- 有效分母：{report['kb_cases']} case（v2 导出、case 级口径）",
        f"- 姿势标签待补：{report['pose_pending']} case"
        + ("（pose_family 维度分析分母相应缩小）" if report["pose_pending"] else ""),
        f"- 关联检验规模：Top-{report['top_k']} 模式 × {len(report['feature_dims'])} 维度，"
        f"共 {report['tested_combinations']} 组（多重比较规模，判读时注意）",
        f"- 守门：单侧样本 < {report['n_min']} 不出 RR；RR 为关联非因果，"
        "所有结论仅作为**归因假设**供后续 A/B 验证。",
        "",
        "## 崩坏模式紧迫度排行榜",
        "",
        "| # | 模式 | 出现 case | 平均严重度 | 趋势 | 紧迫度 |",
        "|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(report["ranking"], 1):
        lines.append(
            f"| {i} | {r['mode']} | {r['freq']}/{r['denominator']} "
            f"| {r['severity_weight']} | {r['trend']}（{r['trend_note']}） "
            f"| {r['urgency']} |")
    lines += ["", f"## Top-{report['top_k']} 模式的 Prompt 特征关联证据", ""]
    for mode, dims in report["correlations"].items():
        lines.append(f"### {mode}")
        lines.append("")
        lines.append("| 维度 | 取值 | 暴露侧 | 对照侧 | RR | 置信 | 备注 |")
        lines.append("|---|---|---|---|---|---|---|")
        for dim in report["feature_dims"]:
            for row in dims.get(dim, []):
                rr = row["rr"] if row["rr"] is not None else "—"
                flags = "；".join(row["flags"]) or "—"
                lines.append(
                    f"| {dim} | {row['value']} | {row['exposed']} "
                    f"| {row['control']} | {rr} | {_CONF_LABEL[row['confidence']]} "
                    f"| {flags} |")
        lines.append("")
    lines += [
        "## 判读指引",
        "",
        "- 暴露侧/对照侧格式为 `出现该模式的 case 数/该组 case 总数`，原始计数恒随附，",
        "  请优先看计数再看 RR。",
        "- `★强`：两侧样本足、RR≥2（或 ≤0.5）、非单种子驱动、暴露侧命中 ≥3——",
        "  值得作为下一轮实验的归因假设。",
        "- `△弱`：可算出 RR 但强度或样本勉强，仅作观察项。",
        "- `×证据不足`：样本未过守门线，**不是没有关联，是现在还不能下结论**，",
        "  随数据积累重跑本报告。",
        "",
    ]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="feedback 知识库分析报告")
    ap.add_argument("--kb", default="experiments/cases/feature_kb.jsonl")
    ap.add_argument("--versions", default="experiments/cases/prompt_versions.yaml")
    ap.add_argument("--out", required=True, help="Markdown 输出路径（同名 .json 一并输出）")
    ap.add_argument("--top-k", type=int, default=TOP_K)
    args = ap.parse_args()

    kb = load_kb(args.kb)
    timeline = load_versions(args.versions)
    report = build_report(kb, timeline, top_k=args.top_k)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        f.write(render_markdown(report))
    json_path = os.path.splitext(args.out)[0] + ".json"
    with open(json_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"报告已输出: {args.out} / {json_path}")


if __name__ == "__main__":
    main()
