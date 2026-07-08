"""崩坏分类活字典：加载、校验、按 aliases 链式归一。数据在 experiments/cases/taxonomy.yaml。"""
from dataclasses import dataclass

import yaml

_MAX_ALIAS_HOPS = 16


@dataclass(frozen=True)
class Taxonomy:
    version: str
    tags: dict          # 父 -> [子, ...]
    aliases: dict       # "旧父/旧子" -> "新父/新子"

    def is_valid(self, tag: str) -> bool:
        parts = tag.split("/")
        if len(parts) != 2:
            return False
        parent, child = parts
        return parent in self.tags and child in self.tags[parent]

    def normalize(self, tag: str) -> str:
        seen = set()
        cur = tag
        hops = 0
        while cur in self.aliases:
            if cur in seen or hops >= _MAX_ALIAS_HOPS:
                raise ValueError(f"tag alias 成环或过深: {tag}")
            seen.add(cur)
            cur = self.aliases[cur]
            hops += 1
        if not self.is_valid(cur):
            raise ValueError(f"未知崩坏 tag（归一后 {cur}）: {tag}")
        return cur

    def parent_of(self, tag: str) -> str:
        return self.normalize(tag).split("/")[0]


def load_taxonomy(path: str) -> Taxonomy:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    tags = {str(k): [str(c) for c in (v or [])]
            for k, v in (raw.get("tags") or {}).items()}
    if not tags:
        raise ValueError("taxonomy 缺少 tags")
    aliases = {str(k): str(v) for k, v in (raw.get("aliases") or {}).items()}
    return Taxonomy(version=str(raw.get("version", "")),
                    tags=tags, aliases=aliases)
