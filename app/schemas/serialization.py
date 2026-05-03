"""Pydantic 字段类型：JSON 序列化为东八区 ISO 字符串。"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import PlainSerializer

from app.datetime_display import format_api_datetime


def _serialize_api_datetime(dt: datetime) -> str:
    return format_api_datetime(dt)


ApiDateTime = Annotated[
    datetime,
    PlainSerializer(_serialize_api_datetime, when_used="json"),
]
