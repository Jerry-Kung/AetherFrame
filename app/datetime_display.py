"""
东八区（Asia/Shanghai）时间展示：应用日志与 API JSON 中的日期时间统一按 UTC+8 格式化。

数据库存储仍按原有约定（通常为 UTC 的 naive datetime）；仅在输出与日志中转换为东八区。
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Optional, Union
from zoneinfo import ZoneInfo

TZ_UTC8 = ZoneInfo("Asia/Shanghai")


def assume_utc_if_naive(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def format_api_datetime(dt: Optional[Union[datetime, str]]) -> str:
    """供 API / 历史 JSON 使用的 ISO 8601 字符串（带 +08:00）。已是字符串时原样返回。"""
    if dt is None:
        return ""
    if isinstance(dt, str):
        return dt
    return assume_utc_if_naive(dt).astimezone(TZ_UTC8).isoformat(timespec="seconds")


def logging_time_converter(ts: float) -> time.struct_time:
    """作为 logging.Formatter 的 converter，使 %(asctime)s 为东八区墙钟时间。"""
    return datetime.fromtimestamp(ts, tz=TZ_UTC8).timetuple()


def _utc8_log_formatter() -> logging.Formatter:
    fmt = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    fmt.converter = logging_time_converter  # type: ignore[assignment]
    return fmt


def configure_logging(level: int = logging.INFO) -> None:
    """配置根日志与已有 StreamHandler，统一使用东八区时间戳。"""
    formatter = _utc8_log_formatter()
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        root.addHandler(handler)
    else:
        for h in root.handlers:
            if isinstance(h, logging.StreamHandler):
                h.setFormatter(formatter)
    root.setLevel(level)


def refresh_stream_handler_timezones() -> None:
    """在 uvicorn 挂载 Handler 之后，为已有 Formatter 打上东八区 converter，保留各 logger 原有格式串。"""
    for lg in logging.Logger.manager.loggerDict.values():
        if not isinstance(lg, logging.Logger):
            continue
        for h in lg.handlers:
            if isinstance(h, logging.StreamHandler):
                f = h.formatter
                if isinstance(f, logging.Formatter):
                    f.converter = logging_time_converter  # type: ignore[assignment]
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        for h in lg.handlers:
            if isinstance(h, logging.StreamHandler):
                f = h.formatter
                if isinstance(f, logging.Formatter):
                    f.converter = logging_time_converter  # type: ignore[assignment]
