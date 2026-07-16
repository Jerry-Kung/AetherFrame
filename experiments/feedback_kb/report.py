"""带证据的分析报告 v2（归因层重构设计 §5）：排行榜 + 词汇假说验证 → JSON + Markdown。
全确定性；趋势只入紧迫度公式与行内展示，不单列章节。

归因层已换向词汇层（配置维度关联按用户判定删除）：证据来自
`experiments/cases/lexical_hypotheses.yaml` 登记假说的全库验证，
检验数 = 假说数（预注册性质）。假说来源见 contrast.py 素材包 + 对话精读。"""
import argparse
import json
import os
from datetime import datetime

from experiments.feedback_kb.kb_query import load_kb, load_tag_taxonomy_map
from experiments.feedback_kb.lexicon_verify import (DEFAULT_HYPOTHESES, N_MIN,
                                                    load_hypotheses, verify_all)
from experiments.feedback_kb.rank import rank_modes
from experiments.feedback_kb.versions import load_versions

_CONF_LABEL = {"strong": "★强", "weak": "△弱", "insufficient": "×证据不足"}


def build_report(kb: list, timeline, hypotheses: list) -> dict:
    tag_map = load_tag_taxonomy_map()
    ranking = rank_modes(kb, timeline, tag_map)
    pose_pending = sum(1 for c in kb if not c.get("pose_family"))
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "kb_cases": len(kb),
        "pose_pending": pose_pending,
        "n_min": N_MIN,
        "hypotheses_tested": len(hypotheses),
        "ranking": ranking,
        "lexical_verification": verify_all(kb, hypotheses, tag_map),
    }


def render_markdown(report: dict) -> str:
    lines = [
        "# 生产 Feedback 分析报告（知识库驱动）",
        "",
        f"- 生成时间：{report['generated_at']}",
        f"- 有效分母：{report['kb_cases']} case（v2 导出、case 级口径）",
        f"- 姿势标签待补：{report['pose_pending']} case",
        f"- 词汇假说检验数：{report['hypotheses_tested']}（检验数 = 登记假说数，预注册性质）",
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
    lines += ["", "## 词汇假说验证", ""]
    rows = report["lexical_verification"]
    if not rows:
        lines += ["暂无登记假说。工作流：`python -m experiments.feedback_kb.contrast "
                  "--mode <排行榜靶模式>` 生成对比素材包 → 对话层精读提假说 → 用户确认后"
                  "登记进 `experiments/cases/lexical_hypotheses.yaml` → 重跑本报告。", ""]
    else:
        lines += [
            "| id | 模式 | scope | patterns | 暴露侧 | 对照侧 | RR | 置信 | status | 备注 |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
        for r in rows:
            rr = r["rr"] if r["rr"] is not None else "—"
            pats = " ∨ ".join(r["patterns"])
            if r["min_hits"] > 1:
                pats += f"（≥{r['min_hits']}次）"
            flags = "；".join(r["flags"]) or "—"
            lines.append(
                f"| {r['id']} | {r['mode']} | {r['scope']} | {pats} "
                f"| {r['exposed']} | {r['control']} | {rr} "
                f"| {_CONF_LABEL[r['confidence']]} | {r['status']} | {flags} |")
        lines.append("")
    lines += [
        "## 判读指引",
        "",
        "- 暴露侧 = 假说 patterns 命中的 case；两侧格式为 `出现该模式的 case 数/该组 case 总数`，",
        "  原始计数恒随附，请优先看计数再看 RR。",
        "- `★强`：两侧样本足、RR≥2（或 ≤0.5）、非单种子驱动、暴露侧命中 ≥3——",
        "  值得作为下一轮实验的归因假设。",
        "- `△弱`：可算出 RR 但强度或样本勉强，仅作观察项。",
        "- `×证据不足`：样本未过守门线，**不是没有关联，是现在还不能下结论**，",
        "  随数据积累重跑本报告。",
        "- status 由人工在查看验证数据后更新（candidate → supported / refuted / retired）。",
        "",
    ]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="feedback 知识库分析报告")
    ap.add_argument("--kb", default="experiments/cases/feature_kb.jsonl")
    ap.add_argument("--versions", default="experiments/cases/prompt_versions.yaml")
    ap.add_argument("--hypotheses", default=DEFAULT_HYPOTHESES)
    ap.add_argument("--out", required=True, help="Markdown 输出路径（同名 .json 一并输出）")
    args = ap.parse_args()

    kb = load_kb(args.kb)
    timeline = load_versions(args.versions)
    hypotheses = load_hypotheses(args.hypotheses)
    report = build_report(kb, timeline, hypotheses)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        f.write(render_markdown(report))
    json_path = os.path.splitext(args.out)[0] + ".json"
    with open(json_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"报告已输出: {args.out} / {json_path}")


if __name__ == "__main__":
    main()
