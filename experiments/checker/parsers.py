"""视觉 LLM 应答解析。宽容解析：失败返回 None/unsure，不抛异常。"""
import re
from typing import Optional

_CN_NUM = {"零": 0, "一": 1, "两": 2, "二": 2, "三": 3, "四": 4,
           "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
_YES_PAT = re.compile(r"^\s*[\*\s（(【\[]*\s*(是|yes)", re.IGNORECASE)
_NO_PAT = re.compile(r"^\s*[\*\s（(【\[]*\s*(否|不是|没有|no)", re.IGNORECASE)
_UNSURE_PAT = re.compile(r"无法判断|不确定|难以判断|unsure|cannot", re.IGNORECASE)


def parse_count_answer(text: str) -> Optional[int]:
    s = (text or "").strip()
    m = re.search(r"\d+", s)
    if m:
        return int(m.group())
    for ch in s:
        if ch in _CN_NUM:
            return _CN_NUM[ch]
    return None


def parse_yes_no_reason(text: str) -> dict:
    s = (text or "").strip()
    verdict = None
    if _NO_PAT.match(s):
        verdict = "no"
    elif _YES_PAT.match(s):
        verdict = "yes"
    reason = re.sub(r"^\s*(是|否|不是|没有|yes|no)[，。,.:：\s]*", "", s,
                    count=1, flags=re.IGNORECASE).strip()
    return {"verdict": verdict, "reason": reason}


def parse_anchor_answer(text: str) -> str:
    s = (text or "").strip()
    if _UNSURE_PAT.search(s):
        return "unsure"
    if _NO_PAT.match(s):
        return "no"
    if _YES_PAT.match(s):
        return "yes"
    return "unsure"
