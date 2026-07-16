"""崩坏模式紧迫度排序（设计文档 §5）：urgency = freq × severity_weight × trend_factor。
全确定性，case 级口径（与 case_analyze 同构）。"""
from experiments.feedback_kb.kb_query import (case_severities, case_taxonomies,
                                              load_tag_taxonomy_map)

TREND_CLAMP = (0.5, 2.0)
# 版本内 case 数低于此值时 trend 取中性 1.0（与 correlate 的 N_min 同源，见设计 §4）
TREND_MIN_CASES = 8


def _mode_rate(cases: list, mode: str, tag_map: dict) -> float:
    hit = sum(1 for c in cases if mode in case_taxonomies(c, tag_map))
    return hit / len(cases) if cases else 0.0


def trend_factor(kb: list, mode: str, timeline, tag_map: dict) -> tuple:
    """(factor, note)。取时间线中实际有数据的最后两个版本对比；样本不足或版本单一取 1.0。"""
    by_ver = {}
    for c in kb:
        by_ver.setdefault(c["version_inferred"], []).append(c)
    present = [v for v in timeline.ordered_versions if v in by_ver]
    if len(present) < 2:
        return 1.0, "单版本数据，趋势中性"
    latest, prev = by_ver[present[-1]], by_ver[present[-2]]
    if len(latest) < TREND_MIN_CASES or len(prev) < TREND_MIN_CASES:
        return 1.0, "版本样本不足，趋势中性"
    prev_rate = _mode_rate(prev, mode, tag_map)
    if prev_rate == 0:
        return 1.0, "上一版本零出现，趋势中性"
    factor = _mode_rate(latest, mode, tag_map) / prev_rate
    lo, hi = TREND_CLAMP
    return max(lo, min(hi, factor)), f"{present[-2]}→{present[-1]}"


def rank_modes(kb: list, timeline, tag_map: dict = None) -> list:
    """按 urgency 降序返回 [{mode, freq, denominator, severity_weight, trend, trend_note,
    urgency}]。mode = 崩坏 taxonomy 子类（case 级去重计数）。"""
    tag_map = tag_map if tag_map is not None else load_tag_taxonomy_map()
    modes = sorted({t for c in kb for t in case_taxonomies(c, tag_map)})
    rows = []
    for mode in modes:
        freq = sum(1 for c in kb if mode in case_taxonomies(c, tag_map))
        sevs = [s for c in kb for s in case_severities(c, mode, tag_map)]
        severity_weight = round(sum(sevs) / len(sevs), 2) if sevs else 1.0
        trend, trend_note = trend_factor(kb, mode, timeline, tag_map)
        rows.append({
            "mode": mode, "freq": freq, "denominator": len(kb),
            "severity_weight": severity_weight,
            "trend": round(trend, 2), "trend_note": trend_note,
            "urgency": round(freq * severity_weight * trend, 2),
        })
    rows.sort(key=lambda r: r["urgency"], reverse=True)
    return rows
