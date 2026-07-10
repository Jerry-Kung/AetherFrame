"""生产 feedback 标签配置：加载 app/config/feedback_tags.yaml 并提供校验/推导/视图。

设计文档：docs/superpowers/specs/2026-07-09-feedback-tag-selection-design.md §1/§3
配置加载失败一律降级 {"version": 0, "tags": []}（前端退化纯文本模式），不阻断反馈链路。
"""

import copy
import logging
import os
from functools import lru_cache
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

_APP_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_PATH = os.path.join(_APP_DIR, "config", "feedback_tags.yaml")

SEVERITIES = ("minor", "moderate", "severe")
DEFAULT_SEVERITY = "moderate"
SEVERITY_LABELS = {"minor": "轻微", "moderate": "中等", "severe": "严重"}

_EMPTY_CONFIG: Dict[str, Any] = {"version": 0, "tags": []}
_POLARITIES = ("positive", "negative", "neutral")


def load_tag_config(path: str = CONFIG_PATH) -> Dict[str, Any]:
    """读取并规整标签配置；任何失败降级空配置并告警。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    except Exception:
        logger.warning("feedback 标签配置加载失败，降级空词表: %s", path, exc_info=True)
        return dict(_EMPTY_CONFIG)
    if not isinstance(raw, dict) or not isinstance(raw.get("tags"), list):
        logger.warning("feedback 标签配置结构非法，降级空词表: %s", path)
        return dict(_EMPTY_CONFIG)

    tags: List[Dict[str, Any]] = []
    for t in raw["tags"]:
        if not isinstance(t, dict):
            continue
        key = str(t.get("key") or "").strip()
        label = str(t.get("label") or "").strip()
        polarity = str(t.get("polarity") or "").strip()
        if not key or not label or polarity not in _POLARITIES:
            logger.warning("feedback 标签条目非法，跳过: %r", t)
            continue
        entry: Dict[str, Any] = {"key": key, "label": label, "polarity": polarity}
        if polarity == "negative":
            entry["leg_foot_bad"] = bool(t.get("leg_foot_bad", False))
            entry["taxonomy"] = str(t.get("taxonomy") or "其他/未分类").strip()
            entry["group"] = str(t.get("group") or "其他").strip()
        tags.append(entry)
    try:
        version = int(raw.get("version") or 0)
    except (TypeError, ValueError):
        version = 0
    return {"version": version, "tags": tags}


@lru_cache(maxsize=1)
def get_tag_config() -> Dict[str, Any]:
    """进程级缓存的仓库配置（改配置文件后重启生效）。"""
    return load_tag_config()


def _tag_map(config: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {t["key"]: t for t in config.get("tags", [])}


def normalize_selected_tags(
    raw: Optional[List[Dict[str, Any]]], config: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """校验归一化选中标签：剔未知 key（告警）、去重保序、severity 兜底/剥离。"""
    known = _tag_map(config)
    out: List[Dict[str, Any]] = []
    seen: set = set()
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").strip()
        if key in seen:
            continue
        tag = known.get(key)
        if tag is None:
            logger.warning("feedback 保存：未知标签 key 已剔除: %r", key)
            continue
        seen.add(key)
        if tag["polarity"] == "negative":
            sev = str(item.get("severity") or "").strip()
            if sev not in SEVERITIES:
                sev = DEFAULT_SEVERITY
            out.append({"key": key, "severity": sev})
        else:
            out.append({"key": key})
    return out


def derive_leg_foot_bad(
    normalized: List[Dict[str, Any]], checkbox: bool, config: Dict[str, Any]
) -> bool:
    """落库 leg_foot_bad = 任一选中负面标签 leg_foot_bad=true OR 兜底勾选。"""
    known = _tag_map(config)
    for item in normalized:
        tag = known.get(item.get("key"))
        if tag is not None and tag.get("leg_foot_bad"):
            return True
    return bool(checkbox)


def tags_for_api(config: Dict[str, Any]) -> Dict[str, Any]:
    """前端下发视图：剥离 taxonomy（前端用不到），leg_foot_bad 统一补齐布尔，group 下发（非负面为 None）。"""
    return {
        "version": config.get("version", 0),
        "tags": [
            {
                "key": t["key"],
                "label": t["label"],
                "polarity": t["polarity"],
                "leg_foot_bad": bool(t.get("leg_foot_bad", False)),
                "group": t.get("group"),
            }
            for t in config.get("tags", [])
        ],
    }


def tag_config_snapshot(config: Dict[str, Any]) -> Dict[str, Any]:
    """导出快照：含 taxonomy 的深拷贝，保证导出文件自包含。"""
    return copy.deepcopy(config)
