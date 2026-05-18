"""TosStorageClient 单元测试（mock tos.TosClientV2）。"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from tos.exceptions import TosServerError

from app.tools.beautify.storage import TosStorageClient, _get_tos_client


class _TestCloudStorageConfig:
    endpoint = "tos-cn-beijing.volces.com"
    region = "cn-beijing"
    bucket = "bu-tmp"
    object_prefix = "tmp/"
    access_key_id = "AK_TEST_DO_NOT_LOG"
    secret_access_key = "SK_TEST_DO_NOT_LOG"
    presigned_ttl_seconds = 3600


@pytest.fixture(autouse=True)
def reset_tos_singleton():
    import app.tools.beautify.storage as storage_mod

    storage_mod._tos_client = None
    yield
    storage_mod._tos_client = None


@pytest.fixture
def storage_client():
    with patch("app.tools.beautify.storage._get_tos_client") as mock_get:
        mock_client = MagicMock()
        mock_get.return_value = mock_client
        client = TosStorageClient(_TestCloudStorageConfig)
        client._client = mock_client
        yield client, mock_client


class TestTosStorageClientUpload:
    @patch("app.tools.beautify.storage.time.time", return_value=1731657645.123)
    def test_upload_and_presign_builds_object_key(self, _mock_time, storage_client, tmp_path):
      client, mock_tos = storage_client
      img = tmp_path / "image_1.png"
      img.write_bytes(b"png")

      mock_tos.pre_signed_url.return_value = SimpleNamespace(
          signed_url="https://example.com/signed"
      )

      key, url = client.upload_and_presign(str(img))
      assert key == "tmp/image_1_1731657645123.png"
      assert url == "https://example.com/signed"

      mock_tos.put_object_from_file.assert_called_once_with(
          "bu-tmp", key, str(img)
      )
      mock_tos.pre_signed_url.assert_called_once()

    def test_upload_server_error_does_not_leak_secrets(self, storage_client, tmp_path, caplog):
      client, mock_tos = storage_client
      img = tmp_path / "a.jpg"
      img.write_bytes(b"jpeg")

      resp = MagicMock(request_id="req-123")
      err = TosServerError(
          resp,
          "auth failed",
          "AccessDenied",
          "",
          "tmp/key",
          "AccessDenied",
      )
      mock_tos.put_object_from_file.side_effect = err

      with pytest.raises(TosServerError):
          client.upload_and_presign(str(img))

      log_text = caplog.text
      assert _TestCloudStorageConfig.access_key_id not in log_text
      assert _TestCloudStorageConfig.secret_access_key not in log_text
      assert "req-123" in log_text


class TestTosStorageClientDelete:
    def test_delete_calls_delete_object(self, storage_client):
      client, mock_tos = storage_client
      client.delete("tmp/foo_1.png")
      mock_tos.delete_object.assert_called_once_with("bu-tmp", "tmp/foo_1.png")


class TestTosClientSingleton:
    def test_get_tos_client_reuses_instance(self):
      import app.tools.beautify.storage as storage_mod

      storage_mod._tos_client = None
      with patch("app.tools.beautify.storage.tos.TosClientV2") as mock_cls:
          mock_cls.return_value = MagicMock()
          c1 = _get_tos_client(_TestCloudStorageConfig)
          c2 = _get_tos_client(_TestCloudStorageConfig)
          assert c1 is c2
          mock_cls.assert_called_once_with(
              _TestCloudStorageConfig.access_key_id,
              _TestCloudStorageConfig.secret_access_key,
              _TestCloudStorageConfig.endpoint,
              _TestCloudStorageConfig.region,
          )
