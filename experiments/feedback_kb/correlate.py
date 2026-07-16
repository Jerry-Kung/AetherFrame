"""Prompt 特征 × 崩坏模式关联分析（设计文档 §4）：相对风险 RR + 四道防噪声守门。

守门（逐条落实）：
1. 最小样本 N_MIN=8：任一侧 case 数不足 → insufficient，不出 RR；
2. 单种子驱动检测：暴露侧崩坏信号 ≥60% 来自同一 seed_id → 标记；
3. 多重比较收敛：由调用方（report）限定 Top-K 模式 × 有方差维度，本模块记录检验组数；
4. 置信三档：strong / weak / insufficient；RR 是关联不是因果，报告措辞统一
   "值得作为归因假设验证"。
零对照分母不做 Haldane 修正，直接标"无对照样本"（设计 §4，更诚实）。
"""
from experiments.feedback_kb.kb_query import case_taxonomies, load_tag_taxonomy_map

N_MIN = 8
SINGLE_SEED_SHARE = 0.6
# 有方差的关联维度（shooting_angle/camera_height 几乎无方差，剔除，见设计文档数据现实节）
FEATURE_DIMS = ("aspect_ratio", "gaze_direction", "pose_family")
STRONG_RR = 2.0


def _dim_value(case: dict, dim: str):
    if dim == "pose_family":
        return case.get("pose_family")
    return (case.get("composition") or {}).get(dim)


def _single_seed_flag(exposed_hits: list) -> bool:
    """暴露侧含目标模式的 case 里，同一 seed 占比 ≥ 阈值（且非孤例）→ 疑单种子驱动。"""
    if len(exposed_hits) < 2:
        return False
    counts = {}
    for c in exposed_hits:
        counts[c["seed_id"]] = counts.get(c["seed_id"], 0) + 1
    return max(counts.values()) / len(exposed_hits) >= SINGLE_SEED_SHARE


def correlate(kb: list, mode: str, dim: str, tag_map: dict = None) -> list:
    """对维度 dim 的每个取值 v 检验模式 mode：返回
    [{dim, value, exposed: "a/n1", control: "b/n2", rr, confidence, flags}]。
    confidence ∈ strong|weak|insufficient；rr 为 None 时 flags 说明原因。"""
    tag_map = tag_map if tag_map is not None else load_tag_taxonomy_map()
    known = [c for c in kb if _dim_value(c, dim) is not None]
    values = sorted({_dim_value(c, dim) for c in known})
    out = []
    for v in values:
        exposed = [c for c in known if _dim_value(c, dim) == v]
        control = [c for c in known if _dim_value(c, dim) != v]
        hits_e = [c for c in exposed if mode in case_taxonomies(c, tag_map)]
        hits_c = [c for c in control if mode in case_taxonomies(c, tag_map)]
        a, n1, b, n2 = len(hits_e), len(exposed), len(hits_c), len(control)
        row = {"dim": dim, "value": v,
               "exposed": f"{a}/{n1}", "control": f"{b}/{n2}",
               "rr": None, "confidence": "insufficient", "flags": []}
        if n1 < N_MIN or n2 < N_MIN:
            row["flags"].append(f"样本不足（N_min={N_MIN}）")
            out.append(row)
            continue
        if b == 0:
            row["flags"].append("无对照样本（对照侧零出现，RR 不可算）")
            row["confidence"] = "weak" if a >= 3 else "insufficient"
            out.append(row)
            continue
        rr = (a / n1) / (b / n2)
        row["rr"] = round(rr, 2)
        single_seed = _single_seed_flag(hits_e)
        if single_seed:
            row["flags"].append("疑单种子驱动（暴露侧崩坏 ≥60% 来自同一 seed）")
        notable = rr >= STRONG_RR or (rr > 0 and rr <= 1 / STRONG_RR)
        if notable and a >= 3 and not single_seed:
            row["confidence"] = "strong"
        else:
            row["confidence"] = "weak"
        out.append(row)
    return out


def correlate_top_modes(kb: list, top_modes: list, tag_map: dict = None) -> dict:
    """对 Top-K 模式 × 全部有方差维度做检验（多重比较收敛在此收口）。
    返回 {"tested_combinations": int, "findings": {mode: {dim: rows}}}。"""
    tag_map = tag_map if tag_map is not None else load_tag_taxonomy_map()
    findings, tested = {}, 0
    for mode in top_modes:
        findings[mode] = {}
        for dim in FEATURE_DIMS:
            rows = correlate(kb, mode, dim, tag_map)
            findings[mode][dim] = rows
            tested += len(rows)
    return {"tested_combinations": tested, "findings": findings}
