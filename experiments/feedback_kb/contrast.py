"""对比精读素材包生成（归因层重构设计 §3）：崩坏组 vs 对照组完整 Prompt 并排输出。

供对话层 LLM 整段精读、提出词汇层归因假说。对照组按姿势族分层、确定性抽样
（排序取样，不用随机）——同姿势配对能让措辞差异更凸显。素材包是消耗品，
输出到 experiments/results/（gitignore 区）。
"""
import argparse
import os
from datetime import date

from experiments.feedback_kb.kb_query import (case_severities, case_taxonomies,
                                              load_kb, load_tag_taxonomy_map)

DEFAULT_KB = "experiments/cases/feature_kb.jsonl"
DEFAULT_OUT_DIR = "experiments/results"
GROUP_CAP = 15

_GUIDE = """\
## 精读指引（给分析 LLM）

逐份对比【崩坏组】与【对照组】的 Prompt 全文（含种子文本），找出**崩坏组特有、
对照组少见**的措辞模式。已知先例：解剖词过密（足弓/脚背/脚趾反复出现）勾引注意力
导致"足部解剖图"；过度文学化描述（如"含情脉脉"）触发 LLM 胡编细节。
注意：模板固定段两组措辞相同（rulepack 已同质化），差异主要在自由发挥区
（场景、姿势描写、表情、角色特有描述、种子用词）。

产出的每条假说必须**可检测**，按以下格式给出，供登记进
`experiments/cases/lexical_hypotheses.yaml` 后由 lexicon_verify 全库验证：

- mode: 目标崩坏模式（本素材包即 {mode}）
- scope: 作用段落（标题包含匹配，如 `角色姿势`；全文用 `full`）
- patterns: 正则列表（命中总次数 >= min_hits 判为暴露）
- min_hits / rationale（一句话机理猜想）
"""


def _mode_max_severity(case: dict, mode: str, tag_map: dict) -> int:
    sevs = case_severities(case, mode, tag_map)
    return max(sevs) if sevs else 0


def split_groups(kb: list, mode: str, tag_map: dict = None, cap: int = GROUP_CAP):
    """返回 (exposed, control)。暴露组取该模式 severity 最重的 case 优先（确定性）；
    对照组按暴露组的姿势族分布分层配对，不足时从余量顺序补齐。"""
    tag_map = tag_map if tag_map is not None else load_tag_taxonomy_map()
    exposed_all = [c for c in kb if mode in case_taxonomies(c, tag_map)]
    exposed_all.sort(key=lambda c: (-_mode_max_severity(c, mode, tag_map), c["case_key"]))
    exposed = exposed_all[:cap]

    pool = sorted((c for c in kb if mode not in case_taxonomies(c, tag_map)),
                  key=lambda c: c["case_key"])
    target = min(len(exposed), len(pool))
    control, used = [], set()
    # 分层：按暴露组各姿势族数量，从对照池同族取样
    pose_need = {}
    for c in exposed:
        pf = c.get("pose_family") or "unknown"
        pose_need[pf] = pose_need.get(pf, 0) + 1
    for pf, need in sorted(pose_need.items()):
        picked = [c for c in pool if (c.get("pose_family") or "unknown") == pf][:need]
        for c in picked:
            control.append(c)
            used.add(c["case_key"])
    for c in pool:  # 余量顺序补齐到与暴露组同规模
        if len(control) >= target:
            break
        if c["case_key"] not in used:
            control.append(c)
            used.add(c["case_key"])
    control = control[:target]
    return exposed, control


def _render_case(c: dict, mode: str, tag_map: dict) -> list:
    lines = [f"#### {c['case_id']}（{c['character_name']}，姿势族 {c.get('pose_family')}）", ""]
    fb = []
    for im in c["images"]:
        tags = [f"{k}({s})" if s else k
                for k, s in zip(im["tag_keys"], im["severities"])
                if k in tag_map or im["leg_foot_bad"]]
        if tags or im["feedback_text"]:
            fb.append(f"- 图{im['image_index']}: {', '.join(tags) or '（无负面标签）'}"
                      + (f" — {im['feedback_text']}" if im["feedback_text"] else ""))
    lines += ["**人工反馈**：", *(fb or ["- （本 case 无负面标签）"]), "",
              f"**种子文本**：{c['seed_text']}", "",
              "**完整 Prompt**：", "```", c["full_prompt"].strip(), "```", ""]
    return lines


def render_bundle(mode: str, exposed: list, control: list, tag_map: dict = None) -> str:
    tag_map = tag_map if tag_map is not None else load_tag_taxonomy_map()
    lines = [f"# 对比精读素材包：{mode}", "",
             f"- 崩坏组 {len(exposed)} case / 对照组 {len(control)} case"
             f"（姿势族分层配对，确定性抽样）", "",
             _GUIDE.format(mode=mode), "",
             f"## 崩坏组（出现 {mode}）", ""]
    for c in exposed:
        lines += _render_case(c, mode, tag_map)
    lines += [f"## 对照组（未出现 {mode}）", ""]
    for c in control:
        lines += _render_case(c, mode, tag_map)
    return "\n".join(lines)


def build_contrast(kb_path: str, mode: str, out_dir: str,
                   cap: int = GROUP_CAP, stamp: str = None) -> str:
    kb = load_kb(kb_path)
    tag_map = load_tag_taxonomy_map()
    exposed, control = split_groups(kb, mode, tag_map, cap=cap)
    if not exposed:
        raise SystemExit(f"KB 中没有出现模式「{mode}」的 case，请核对 taxonomy 名称")
    stamp = stamp or date.today().strftime("%Y%m%d")
    slug = mode.replace("/", "_")
    out_path = os.path.join(out_dir, f"contrast_{slug}_{stamp}.md")
    os.makedirs(out_dir, exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(render_bundle(mode, exposed, control, tag_map))
    return out_path


def main():
    ap = argparse.ArgumentParser(description="生成崩坏模式对比精读素材包")
    ap.add_argument("--mode", required=True, help="崩坏 taxonomy，如 腿部/结构错误")
    ap.add_argument("--kb", default=DEFAULT_KB)
    ap.add_argument("--out", default=DEFAULT_OUT_DIR, help="输出目录")
    ap.add_argument("--cap", type=int, default=GROUP_CAP, help="每组 case 数上限")
    args = ap.parse_args()
    path = build_contrast(args.kb, args.mode, args.out, cap=args.cap)
    print(f"素材包已输出: {path}")


if __name__ == "__main__":
    main()
