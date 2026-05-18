import json
import logging
from dataclasses import dataclass
from typing import Literal, Protocol

import requests

from app.tools.beautify.config import EnhancerConfig

logger = logging.getLogger(__name__)


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
            raise RuntimeError(f"bigjpg submit request failed: {exc}") from exc

        if not response.ok:
            body = (response.text or "")[:500]
            raise RuntimeError(f"HTTP {response.status_code}: {body}")

        data = response.json()
        tid = data.get("tid")
        if not tid:
            raise ValueError("bigjpg submit response missing tid")

        remaining = data.get("remaining_api_calls")
        logger.debug("bigjpg submit ok tid=%s remaining_api_calls=%s", tid, remaining)
        return str(tid)

    def poll(self, external_task_id: str) -> EnhanceResult:
        try:
            response = requests.get(
                self._poll_url(external_task_id),
                headers=self._api_key_header(),
                timeout=self._config.poll_timeout_seconds,
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"bigjpg poll request failed: {exc}") from exc

        if not response.ok:
            body = (response.text or "")[:500]
            raise RuntimeError(f"HTTP {response.status_code}: {body}")

        data = response.json()
        inner = data.get(external_task_id)
        if not isinstance(inner, dict):
            return EnhanceResult(
                status="failed",
                error=f"unexpected poll payload keys: {list(data.keys())[:10]}",
            )

        raw_status = inner.get("status")
        if raw_status == "process":
            return EnhanceResult(status="running")
        if raw_status == "success":
            return EnhanceResult(status="succeeded", result_url=inner.get("url") or None)

        return EnhanceResult(
            status="failed",
            error=json.dumps(inner, ensure_ascii=False)[:500],
        )


_default_enhancer: BigjpgEnhancer | None = None


def get_default_enhancer() -> ImageEnhancer:
    global _default_enhancer
    if _default_enhancer is None:
        _default_enhancer = BigjpgEnhancer()
    return _default_enhancer
