"""图片生成类任务的统一超时规则（期望张数 × 固定分钟）。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

IMAGE_GEN_MINUTES_PER_IMAGE = 20

IMAGE_GEN_TIMEOUT_ERROR_MESSAGE = (
    "等待超时，已自动终止任务（已超过「本次需生成图片张数 × 20 分钟」的等待上限）。"
)

IMAGE_GEN_RESTART_ERROR_MESSAGE = (
    "服务已重启，后台图片生成任务已中断，请重新提交。"
)


def timeout_seconds(image_count: int) -> int:
    n = max(1, int(image_count))
    return n * IMAGE_GEN_MINUTES_PER_IMAGE * 60


def _to_utc_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def deadline_exceeded(
    anchor: Optional[datetime],
    image_count: int,
    *,
    now: Optional[datetime] = None,
) -> bool:
    """
    若 anchor 为 None，视为未超时（避免误杀）。
    """
    if anchor is None:
        return False
    current = now or datetime.now(timezone.utc)
    elapsed = current - _to_utc_aware(anchor)
    return elapsed >= timedelta(seconds=timeout_seconds(image_count))
