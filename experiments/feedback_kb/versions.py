"""Prompt 版本时间线（设计文档 §7）：加载 + 按 created_at 推断版本（方式一时间戳近似）。"""
from dataclasses import dataclass
from datetime import datetime

import yaml


@dataclass(frozen=True)
class VersionTimeline:
    # [(version, since_datetime_or_None, description)]，按 since 升序，首条 since 为 None
    entries: tuple

    def infer_version(self, created_at: str) -> str:
        """created_at 为 ISO 字符串（导出 JSON 原样）。落入最后一个 since <= created_at 的版本。"""
        ts = datetime.fromisoformat(created_at)
        current = None
        for version, since, _desc in self.entries:
            if since is None or since <= ts:
                current = version
            else:
                break
        if current is None:
            raise ValueError(f"created_at {created_at} 早于时间线全部区间且无基线版本")
        return current

    @property
    def ordered_versions(self) -> list:
        return [v for v, _s, _d in self.entries]


def load_versions(path: str) -> VersionTimeline:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    items = raw.get("versions") or []
    if not items:
        raise ValueError("prompt_versions.yaml 缺少 versions")
    entries = []
    for it in items:
        since = it.get("since")
        entries.append((
            str(it["version"]),
            datetime.fromisoformat(since) if since else None,
            str(it.get("description", "")),
        ))
    # 首条允许 since=None 作基线；其余必须有 since 且升序
    for i in range(1, len(entries)):
        if entries[i][1] is None:
            raise ValueError(f"仅首条允许 since 为空: {entries[i][0]}")
        if entries[i - 1][1] is not None and entries[i][1] <= entries[i - 1][1]:
            raise ValueError(f"versions 必须按 since 升序: {entries[i][0]}")
    return VersionTimeline(entries=tuple(entries))
