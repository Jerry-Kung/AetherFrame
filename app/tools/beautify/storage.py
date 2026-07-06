import logging
import os
import threading
import time
from typing import Protocol

import tos
from tos import HttpMethodType
from tos.exceptions import TosClientError, TosServerError

from app.tools.beautify.config import CloudStorageConfig

logger = logging.getLogger(__name__)

_client_lock = threading.Lock()
_tos_client: tos.TosClientV2 | None = None


class CloudStorageClient(Protocol):
    def upload_and_presign(
        self, local_path: str, object_key: str | None = None
    ) -> tuple[str, str]: ...

    def delete(self, object_key: str) -> None: ...


def _get_tos_client(config: type[CloudStorageConfig]) -> tos.TosClientV2:
    global _tos_client
    if _tos_client is not None:
        return _tos_client
    with _client_lock:
        if _tos_client is None:
            _tos_client = tos.TosClientV2(
                config.access_key_id,
                config.secret_access_key,
                config.endpoint,
                config.region,
            )
    return _tos_client


class TosStorageClient:
    def __init__(self, config: type[CloudStorageConfig] | None = None):
        self._config = config or CloudStorageConfig
        self._client = _get_tos_client(self._config)
        self._bucket = self._config.bucket
        self._prefix = self._config.object_prefix

    def _build_object_key(self, local_path: str) -> str:
        base = os.path.basename(local_path)
        name, ext = os.path.splitext(base)
        ts_ms = int(time.time() * 1000)
        return f"{self._prefix}{name}_{ts_ms}{ext}"

    def upload_and_presign(
        self, local_path: str, object_key: str | None = None
    ) -> tuple[str, str]:
        key = object_key or self._build_object_key(local_path)
        try:
            self._client.put_object_from_file(self._bucket, key, local_path)
            signed = self._client.pre_signed_url(
                HttpMethodType.Http_Method_Get,
                self._bucket,
                key,
                expires=self._config.presigned_ttl_seconds,
            )
        except TosServerError as exc:
            logger.error(
                "TOS upload server error code=%s request_id=%s message=%s",
                exc.code,
                exc.request_id,
                exc.message,
            )
            raise
        except TosClientError as exc:
            logger.error("TOS upload client error message=%s", exc.message)
            raise
        logger.info("TOS upload ok object_key=%s", key)
        return key, signed.signed_url

    def delete(self, object_key: str) -> None:
        try:
            self._client.delete_object(self._bucket, object_key)
        except TosServerError as exc:
            logger.error(
                "TOS delete server error object_key=%s code=%s request_id=%s message=%s",
                object_key,
                exc.code,
                exc.request_id,
                exc.message,
            )
            raise
        except TosClientError as exc:
            logger.error(
                "TOS delete client error object_key=%s message=%s",
                object_key,
                exc.message,
            )
            raise
        logger.info("TOS delete ok object_key=%s", object_key)


_default_storage: TosStorageClient | None = None


def get_default_client() -> CloudStorageClient:
    global _default_storage
    if _default_storage is None:
        _default_storage = TosStorageClient()
    return _default_storage
