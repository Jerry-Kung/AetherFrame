"""知识库读取与检索原语（设计文档 §2 模块表）。分析模块只经由这里读 KB。

tag 维度检索按「原始 tag key → 崩坏 taxonomy」动态映射：KB 存原始 key，
映射从生产标签词表 `app/config/feedback_tags.yaml`（活配置，key 一经启用不复用）
加载——taxonomy v3 落地改该文件后，全库分析自动按新映射重算，无需重建 KB。
"""
import json
import os

import yaml

TAG_CONFIG_PATH = os.path.join("app", "config", "feedback_tags.yaml")

# severity 原始值为英文枚举（导出 selected_tags[].severity），中文仅出现在 label 里
SEVERITY_WEIGHT = {"minor": 1, "moderate": 2, "severe": 3}

_tag_map_cache = {}


def load_tag_taxonomy_map(config_path: str = TAG_CONFIG_PATH) -> dict:
    """负面标签 key → 崩坏 taxonomy 映射（正面/中立无映射，不入表）。进程内缓存。"""
    if config_path not in _tag_map_cache:
        with open(config_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        _tag_map_cache[config_path] = {
            str(t["key"]): str(t["taxonomy"])
            for t in (raw.get("tags") or [])
            if t.get("polarity") == "negative" and t.get("taxonomy")
        }
    return _tag_map_cache[config_path]


def load_kb(kb_path: str) -> list:
    if not os.path.isfile(kb_path):
        raise FileNotFoundError(f"知识库不存在，请先运行 kb_build: {kb_path}")
    rows = []
    with open(kb_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def case_tag_keys(case: dict) -> set:
    """case 内出现过的原始 tag key（跨图去重）。"""
    return {k for im in case["images"] for k in im["tag_keys"]}


def case_taxonomies(case: dict, tag_map: dict = None) -> set:
    """case 内出现过的崩坏 taxonomy（负面标签映射后去重）。"""
    tag_map = tag_map if tag_map is not None else load_tag_taxonomy_map()
    return {tag_map[k] for k in case_tag_keys(case) if k in tag_map}


def case_severities(case: dict, taxonomy: str, tag_map: dict = None) -> list:
    """case 内指向某 taxonomy 的全部 severity 权重值（图级、不去重）。"""
    tag_map = tag_map if tag_map is not None else load_tag_taxonomy_map()
    out = []
    for im in case["images"]:
        for key, sev in zip(im["tag_keys"], im["severities"]):
            if tag_map.get(key) == taxonomy and sev in SEVERITY_WEIGHT:
                out.append(SEVERITY_WEIGHT[sev])
    return out


def filter_cases(kb: list, taxonomy: str = None, version: str = None,
                 pose_family: str = None, character: str = None,
                 min_created_at: str = None) -> list:
    """按维度过滤 case 行（各条件与关系）。taxonomy 匹配 case 内任一图的映射后 tag。"""
    out = []
    for c in kb:
        if taxonomy and taxonomy not in case_taxonomies(c):
            continue
        if version and c["version_inferred"] != version:
            continue
        if pose_family and c.get("pose_family") != pose_family:
            continue
        if character and c["character_name"].lower() != character.lower():
            continue
        if min_created_at and c["created_at"] < min_created_at:
            continue
        out.append(c)
    return out
