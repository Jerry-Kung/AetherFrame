"""词汇假说全库验证（归因层重构设计 §4）：假说库 → 逐条在 KB 上算 RR + 守门 + 置信。

归因闭环分工：LLM 在对话层精读对比素材包提出**可检测**的措辞假说（pattern + scope），
用户确认后登记进 `experiments/cases/lexical_hypotheses.yaml`；本模块做确定性验证——
按 scope 段落正则计命中划分暴露/对照组，复用 RR 统计核心。检验数 = 假说数（预注册性质，
比全维度扫描的多重比较面收敛得多）。

统计核心与四道守门沿自 v1 correlate（配置维度扫描已按用户判定删除，守门语义不变）：
1. 最小样本 N_MIN=8：任一侧 case 数不足 → insufficient，不出 RR；
2. 单种子驱动检测：暴露侧崩坏信号 ≥60% 来自同一 seed_id → 标记；
3. 置信三档：strong / weak / insufficient；RR 是关联不是因果，报告措辞统一
   "值得作为归因假设验证"；
4. 零对照分母不做 Haldane 修正，直接标"无对照样本"（更诚实）。
"""
import re

import yaml

from experiments.feedback_kb import features
from experiments.feedback_kb.kb_query import case_taxonomies, load_tag_taxonomy_map

N_MIN = 8
SINGLE_SEED_SHARE = 0.6
STRONG_RR = 2.0

DEFAULT_HYPOTHESES = "experiments/cases/lexical_hypotheses.yaml"

_SCOPE_FULL = "full"


def load_hypotheses(path: str = DEFAULT_HYPOTHESES) -> list:
    """假说库条目列表（可为空）。id 不复用；status 为假说生命周期状态，人工维护。"""
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    hyps = raw.get("hypotheses") or []
    seen = set()
    for h in hyps:
        for field in ("id", "mode", "scope", "patterns"):
            if not h.get(field):
                raise ValueError(f"假说缺少必填字段 {field}: {h}")
        if h["id"] in seen:
            raise ValueError(f"假说 id 重复（id 不复用）: {h['id']}")
        seen.add(h["id"])
    return hyps


def scope_text(full_prompt: str, scope: str) -> str:
    """按 scope 取正文：'full' = 全文；否则取标题包含 scope 的所有段正文拼接。"""
    if scope == _SCOPE_FULL:
        return full_prompt
    sections = features.split_sections(full_prompt)
    return "\n".join(body for title, body in sections.items() if scope in title)


def hypothesis_hits(case: dict, hyp: dict) -> int:
    """该 case 对假说 patterns 的命中总次数（在 scope 段内，正则、可重叠词形分别计）。"""
    text = scope_text(case.get("full_prompt") or "", hyp["scope"])
    return sum(len(re.findall(p, text)) for p in hyp["patterns"])


def _single_seed_flag(exposed_hits: list) -> bool:
    """暴露侧含目标模式的 case 里，同一 seed 占比 ≥ 阈值（且非孤例）→ 疑单种子驱动。"""
    if len(exposed_hits) < 2:
        return False
    counts = {}
    for c in exposed_hits:
        counts[c["seed_id"]] = counts.get(c["seed_id"], 0) + 1
    return max(counts.values()) / len(exposed_hits) >= SINGLE_SEED_SHARE


def rr_contrast(exposed: list, control: list, mode: str, tag_map: dict = None) -> dict:
    """RR 统计核心：给定暴露/对照两组 case，检验模式 mode 的出现率差异。
    返回 {exposed: "a/n1", control: "b/n2", rr, confidence, flags}。"""
    tag_map = tag_map if tag_map is not None else load_tag_taxonomy_map()
    hits_e = [c for c in exposed if mode in case_taxonomies(c, tag_map)]
    hits_c = [c for c in control if mode in case_taxonomies(c, tag_map)]
    a, n1, b, n2 = len(hits_e), len(exposed), len(hits_c), len(control)
    row = {"exposed": f"{a}/{n1}", "control": f"{b}/{n2}",
           "rr": None, "confidence": "insufficient", "flags": []}
    if n1 < N_MIN or n2 < N_MIN:
        row["flags"].append(f"样本不足（N_min={N_MIN}）")
        return row
    if b == 0:
        row["flags"].append("无对照样本（对照侧零出现，RR 不可算）")
        row["confidence"] = "weak" if a >= 3 else "insufficient"
        return row
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
    return row


def verify_hypothesis(kb: list, hyp: dict, tag_map: dict = None) -> dict:
    """单条假说验证：命中次数 >= min_hits（默认 1）划暴露组，其余为对照组。"""
    min_hits = int(hyp.get("min_hits", 1))
    exposed = [c for c in kb if hypothesis_hits(c, hyp) >= min_hits]
    control = [c for c in kb if hypothesis_hits(c, hyp) < min_hits]
    row = rr_contrast(exposed, control, hyp["mode"], tag_map)
    row.update({"id": hyp["id"], "mode": hyp["mode"], "scope": hyp["scope"],
                "patterns": list(hyp["patterns"]), "min_hits": min_hits,
                "status": hyp.get("status", "candidate")})
    return row


def verify_all(kb: list, hypotheses: list, tag_map: dict = None) -> list:
    tag_map = tag_map if tag_map is not None else load_tag_taxonomy_map()
    return [verify_hypothesis(kb, h, tag_map) for h in hypotheses]
