"""姿势族活字典（设计文档 §6）：加载、校验、aliases 归一。数据在 experiments/cases/pose_taxonomy.yaml。
结构与 casebank/taxonomy.py 同范式（只增不改、aliases 链式归一），但姿势族是单层枚举。"""
from dataclasses import dataclass

import yaml

_MAX_ALIAS_HOPS = 16


@dataclass(frozen=True)
class PoseTaxonomy:
    version: str
    families: dict        # 族名 -> 中文描述（供 LLM 打标 prompt 使用）
    aliases: dict         # 旧族名 -> 新族名

    def is_valid(self, family: str) -> bool:
        return family in self.families

    def normalize(self, family: str) -> str:
        seen = set()
        cur = family
        hops = 0
        while cur in self.aliases:
            if cur in seen or hops >= _MAX_ALIAS_HOPS:
                raise ValueError(f"姿势族 alias 成环或过深: {family}")
            seen.add(cur)
            cur = self.aliases[cur]
            hops += 1
        if not self.is_valid(cur):
            raise ValueError(f"未知姿势族（归一后 {cur}）: {family}")
        return cur


def load_pose_taxonomy(path: str) -> PoseTaxonomy:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    families = {str(k): str(v) for k, v in (raw.get("families") or {}).items()}
    if not families:
        raise ValueError("pose_taxonomy 缺少 families")
    if "other" not in families:
        raise ValueError("pose_taxonomy 必须含 other 兜底族")
    aliases = {str(k): str(v) for k, v in (raw.get("aliases") or {}).items()}
    return PoseTaxonomy(version=str(raw.get("version", "")),
                        families=families, aliases=aliases)
