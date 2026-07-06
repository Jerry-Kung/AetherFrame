import json
import logging
from dataclasses import dataclass
from typing import Literal, Protocol

import requests

from app.tools.beautify.config import EnhancerConfig

logger = logging.getLogger(__name__)

# 已知的「进行中」状态：bigjpg 在不同阶段返回不同字符串
# - new      → 任务刚提交，尚未进入处理队列（submit 之后立即 poll 会看到）
# - process  → 任务处理中
# - wait/queue/pending → 经验性补充（同义词）
RUNNING_STATUSES = frozenset({"new", "process", "wait", "queue", "queued", "running", "pending"})

# 已知的「失败」状态：bigjpg 当前只在样例里见过 success；以下为防御性集合
FAILED_STATUSES = frozenset({"error", "failed", "fail"})

SUCCESS_STATUS = "success"


@dataclass
class EnhanceResult:
    status: Literal["pending", "running", "succeeded", "failed"]
    result_url: str | None = None
    error: str | None = None


class ImageEnhancer(Protocol):
    def submit(self, image_url: str) -> str: ...

    def poll(self, external_task_id: str) -> EnhanceResult: ...


class BigjpgEnhancer:
    def __init__(self, config: type[EnhancerConfig] | None = None):
        self._config = config or EnhancerConfig

    def _api_key_header(self) -> dict[str, str]:
        return {"X-API-KEY": self._config.api_key}

    def _submit_url(self) -> str:
        return f"{self._config.base_url.rstrip('/')}{self._config.submit_path}"

    def _poll_url(self, tid: str) -> str:
        path = self._config.query_path_template.format(tid=tid)
        return f"{self._config.base_url.rstrip('/')}{path}"

    def submit(self, image_url: str) -> str:
        payload = {**self._config.fixed_params, "input": image_url}
        # 不打印 input 的完整预签名 URL（含 X-Tos-Signature 签名参数，敏感）
        logged_payload = {**self._config.fixed_params, "input": "<redacted-presigned-url>"}
        logger.info(
            "bigjpg submit url=%s payload=%s timeout=%ss",
            self._submit_url(),
            logged_payload,
            self._config.submit_timeout_seconds,
        )
        try:
            response = requests.post(
                self._submit_url(),
                headers={
                    **self._api_key_header(),
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self._config.submit_timeout_seconds,
            )
        except requests.RequestException as exc:
            logger.error("bigjpg submit network error: %s", exc)
            raise RuntimeError(f"bigjpg submit request failed: {exc}") from exc

        if not response.ok:
            body = (response.text or "")[:500]
            logger.error(
                "bigjpg submit non-2xx status=%s body=%s",
                response.status_code,
                body,
            )
            raise RuntimeError(f"HTTP {response.status_code}: {body}")

        data = response.json()
        tid = data.get("tid")
        if not tid:
            logger.error("bigjpg submit response missing tid: %s", data)
            raise ValueError("bigjpg submit response missing tid")

        remaining = data.get("remaining_api_calls")
        minute_hint = data.get("minute")
        logger.info(
            "bigjpg submit ok tid=%s remaining_api_calls=%s minute=%s",
            tid,
            remaining,
            minute_hint,
        )
        return str(tid)

    def poll(self, external_task_id: str) -> EnhanceResult:
        url = self._poll_url(external_task_id)
        logger.info("bigjpg poll tid=%s url=%s", external_task_id, url)
        try:
            response = requests.get(
                url,
                headers=self._api_key_header(),
                timeout=self._config.poll_timeout_seconds,
            )
        except requests.RequestException as exc:
            logger.error(
                "bigjpg poll network error tid=%s: %s", external_task_id, exc
            )
            raise RuntimeError(f"bigjpg poll request failed: {exc}") from exc

        if not response.ok:
            body = (response.text or "")[:500]
            logger.error(
                "bigjpg poll non-2xx tid=%s status=%s body=%s",
                external_task_id,
                response.status_code,
                body,
            )
            raise RuntimeError(f"HTTP {response.status_code}: {body}")

        data = response.json()
        inner = data.get(external_task_id)
        if not isinstance(inner, dict):
            logger.error(
                "bigjpg poll unexpected payload tid=%s payload=%s",
                external_task_id,
                json.dumps(data, ensure_ascii=False)[:500],
            )
            return EnhanceResult(
                status="failed",
                error=f"unexpected poll payload keys: {list(data.keys())[:10]}",
            )

        raw_status = inner.get("status")
        inner_url = inner.get("url") or None
        inner_size = inner.get("size")
        logger.info(
            "bigjpg poll resp tid=%s status=%s has_url=%s size=%s",
            external_task_id,
            raw_status,
            bool(inner_url),
            inner_size,
        )

        if raw_status == SUCCESS_STATUS:
            return EnhanceResult(status="succeeded", result_url=inner_url)
        if raw_status in FAILED_STATUSES:
            return EnhanceResult(
                status="failed",
                error=json.dumps(inner, ensure_ascii=False)[:500],
            )
        if raw_status not in RUNNING_STATUSES:
            # 未知 status：保守地继续轮询，由上层 5 分钟总超时兜底
            logger.warning(
                "bigjpg poll unknown status tid=%s status=%r payload=%s",
                external_task_id,
                raw_status,
                json.dumps(inner, ensure_ascii=False)[:500],
            )
        return EnhanceResult(status="running")


_default_enhancer: BigjpgEnhancer | None = None


def get_default_enhancer() -> ImageEnhancer:
    global _default_enhancer
    if _default_enhancer is None:
        _default_enhancer = BigjpgEnhancer()
    return _default_enhancer
