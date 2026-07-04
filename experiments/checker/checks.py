"""第一层结构完整性检查 + 第二层锚点核对。每项独立一次视觉 LLM 调用（spec §5）。"""
import logging

from app.services.material_service.material_file_service import (
    get_standard_slot_image_path,
)
from app.tools.llm.yibu_llm_infer import yibu_gemini_infer

from experiments.checker.parsers import (
    parse_anchor_answer,
    parse_count_answer,
    parse_yes_no_reason,
)

logger = logging.getLogger(__name__)

_SYSTEM = "你是一位严谨的图像质检员，只回答被问到的问题本身，不要输出任何多余内容。"

STRUCTURE_CHECKS = [
    {
        "check_id": "leg_count",
        "kind": "count",
        "question": "图中人物有几条腿？只回答数字。",
    },
    {
        "check_id": "torso_dup",
        "kind": "yes_no",
        "question": "图中是否出现一个以上的上半身/躯干，或躯干与头部数量不匹配？"
                    "请回答“是”或“否”，并给出一句话理由。",
    },
    {
        "check_id": "neck_waist_twist",
        "kind": "yes_no",
        "question": "图中人物的颈部或腰部是否存在违反人体结构的异常扭曲、拉伸或错位？"
                    "请回答“是”或“否”，并给出一句话理由。",
    },
    {
        "check_id": "furniture_broken",
        "kind": "yes_no",
        "question": "图中家具是否存在结构性错误（椅腿数量异常、结构穿插、透视崩塌）？"
                    "请回答“是”或“否”，并给出一句话理由。",
    },
]


def run_structure_checks(image_path: str, infer=yibu_gemini_infer) -> dict:
    out = {}
    for check in STRUCTURE_CHECKS:
        cid = check["check_id"]
        try:
            raw = infer(check["question"], image_path=[image_path],
                        system_instruction=_SYSTEM, thinking_level="low",
                        temperature=0.1)
        except Exception as e:  # 单项失败不阻断其余项
            logger.warning("结构检查 %s 调用失败: %s", cid, e)
            out[cid] = {"kind": check["kind"], "error": str(e) or type(e).__name__}
            continue
        if check["kind"] == "count":
            value = parse_count_answer(raw)
            out[cid] = {"kind": "count", "value": value,
                        "pass": (value == 2) if value is not None else None,
                        "raw": raw}
        else:
            parsed = parse_yes_no_reason(raw)
            verdict = parsed["verdict"]
            out[cid] = {"kind": "yes_no", "verdict": verdict,
                        "reason": parsed["reason"],
                        "pass": (verdict == "no") if verdict else None,
                        "raw": raw}
    return out


def _resolve_ref_slot_path(character_id: str, ref_slot: str) -> str:
    p = get_standard_slot_image_path(character_id, ref_slot)
    if not p:
        raise ValueError(f"角色 {character_id} 缺少参考图槽位 {ref_slot}")
    return p


def run_anchor_checks(image_path: str, character_id: str, anchors,
                      infer=yibu_gemini_infer) -> dict:
    out = {}
    for anchor in anchors:
        try:
            ref = _resolve_ref_slot_path(character_id, anchor.ref_slot)
            prompt = (
                "第一张图是 AI 生成图，第二张图是该角色的官方参考图。"
                f"{anchor.question}"
                "请只回答“是”、“否”或“无法判断”。"
            )
            raw = infer(prompt, image_path=[image_path, ref],
                        system_instruction=_SYSTEM, thinking_level="low",
                        temperature=0.1)
            out[anchor.anchor_id] = {"answer": parse_anchor_answer(raw), "raw": raw}
        except Exception as e:
            logger.warning("锚点核对 %s 调用失败: %s", anchor.anchor_id, e)
            out[anchor.anchor_id] = {"error": str(e) or type(e).__name__}
    return out
