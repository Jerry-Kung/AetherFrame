import logging
import os
import threading
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_MODEL = "doubao-seedance-2-0-260128"

# 模型支持的长宽比（实现时以火山引擎官方文档核对增删）
SUPPORTED_RATIOS = ["16:9", "4:3", "1:1", "3:4", "9:16", "21:9"]


def _ratio_value(ratio: str) -> float:
    w, h = ratio.split(":")
    return int(w) / int(h)


def pick_closest_ratio(width: int, height: int) -> str:
    if not width or not height:
        return "1:1"
    target = width / height
    return min(SUPPORTED_RATIOS, key=lambda r: abs(_ratio_value(r) - target))


@dataclass
class SeedanceResult:
    status: str  # "running" | "succeeded" | "failed"
    video_url: str | None = None
    error: str | None = None


def _get_config() -> tuple[str, str, str]:
    base_url = os.environ.get("SEEDANCE_BASE_URL", DEFAULT_BASE_URL)
    model = os.environ.get("SEEDANCE_MODEL", DEFAULT_MODEL)
    api_key = os.environ.get("SEEDANCE_API_KEY", "")
    return base_url, model, api_key


class SeedanceClient:
    def __init__(self, base_url: str | None = None, model: str | None = None, api_key: str | None = None):
        cfg_base, cfg_model, cfg_key = _get_config()
        self._base_url = base_url or cfg_base
        self._model = model or cfg_model
        self._api_key = api_key or cfg_key
        self._client = None

    def _ark(self):
        if self._client is None:
            if not self._api_key:
                raise RuntimeError("SEEDANCE_API_KEY 未配置，无法调用视频生成模型")
            from volcenginesdkarkruntime import Ark

            self._client = Ark(base_url=self._base_url, api_key=self._api_key)
        return self._client

    def submit(
        self,
        prompt: str,
        image_url: str,
        *,
        image_role: str,
        duration: int,
        generate_audio: bool,
        ratio: str,
    ) -> str:
        image_item = {"type": "image_url", "image_url": {"url": image_url}}
        if image_role == "reference_image":
            image_item["role"] = "reference_image"
        # image_role == "first_frame" 时不带 role，图片作为视频首帧
        result = self._ark().content_generation.tasks.create(
            model=self._model,
            content=[{"type": "text", "text": prompt}, image_item],
            generate_audio=generate_audio,
            ratio=ratio,
            duration=duration,
        )
        return result.id

    def poll(self, task_id: str) -> SeedanceResult:
        res = self._ark().content_generation.tasks.get(task_id=task_id)
        status = res.status
        if status == "succeeded":
            video_url = getattr(res.content, "video_url", None) if res.content else None
            return SeedanceResult(status="succeeded", video_url=video_url)
        if status == "failed":
            return SeedanceResult(status="failed", error=str(res.error))
        return SeedanceResult(status="running")


_default_lock = threading.Lock()
_default_client: SeedanceClient | None = None


def get_default_seedance_client() -> SeedanceClient:
    global _default_client
    if _default_client is None:
        with _default_lock:
            if _default_client is None:
                _default_client = SeedanceClient()
    return _default_client


def download_video(video_url: str, dest_path: str) -> None:
    with requests.get(video_url, stream=True, timeout=120) as resp:
        if not resp.ok:
            body = (resp.text or "")[:500]
            raise RuntimeError(f"视频下载失败 HTTP {resp.status_code}: {body}")
        with open(dest_path, "wb") as out:
            for chunk in resp.iter_content(chunk_size=65536):
                if chunk:
                    out.write(chunk)
