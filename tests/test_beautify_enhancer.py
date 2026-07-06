"""BigjpgEnhancer 单元测试（mock requests）。"""

from unittest.mock import MagicMock, patch

import pytest

from app.tools.beautify.enhancer import BigjpgEnhancer, EnhanceResult


class _TestEnhancerConfig:
    base_url = "https://bigjpg.com"
    submit_path = "/api/task/"
    query_path_template = "/api/task/{tid}"
    api_key = "test-secret-key-do-not-log"
    poll_interval_seconds = 8
    submit_timeout_seconds = 30
    poll_timeout_seconds = 15
    fixed_params = {
        "style": "art",
        "noise": "1",
        "x2": "1",
        "file_name": "main_image.png",
    }


@pytest.fixture
def enhancer():
    return BigjpgEnhancer(_TestEnhancerConfig)


class TestBigjpgEnhancerSubmit:
    @patch("app.tools.beautify.enhancer.requests.post")
    def test_submit_sends_fixed_params(self, mock_post, enhancer):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {
            "tid": "tid-abc",
            "remaining_api_calls": 100,
        }
        mock_post.return_value = mock_resp

        tid = enhancer.submit("https://example.com/image.png")
        assert tid == "tid-abc"

        mock_post.assert_called_once()
        _args, kwargs = mock_post.call_args
        assert kwargs["json"]["style"] == "art"
        assert kwargs["json"]["noise"] == "1"
        assert kwargs["json"]["x2"] == "1"
        assert kwargs["json"]["file_name"] == "main_image.png"
        assert kwargs["json"]["input"] == "https://example.com/image.png"
        assert kwargs["headers"]["X-API-KEY"] == _TestEnhancerConfig.api_key

    @patch("app.tools.beautify.enhancer.requests.post")
    def test_submit_http_error_raises_without_key(self, mock_post, enhancer):
        mock_resp = MagicMock()
        mock_resp.ok = False
        mock_resp.status_code = 500
        mock_resp.text = "server exploded"
        mock_post.return_value = mock_resp

        with pytest.raises(RuntimeError) as exc_info:
            enhancer.submit("https://example.com/image.png")
        msg = str(exc_info.value)
        assert "HTTP 500" in msg
        assert _TestEnhancerConfig.api_key not in msg


class TestBigjpgEnhancerPoll:
    @patch("app.tools.beautify.enhancer.requests.get")
    def test_poll_process_maps_to_running(self, mock_get, enhancer):
        tid = "tid-abc"
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {
            tid: {"status": "process", "url": "", "size": ""},
        }
        mock_get.return_value = mock_resp

        result = enhancer.poll(tid)
        assert result == EnhanceResult(status="running")

    @patch("app.tools.beautify.enhancer.requests.get")
    def test_poll_success_maps_to_succeeded(self, mock_get, enhancer):
        tid = "tid-abc"
        url = "https://cdn.example.com/out.png"
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {
            tid: {"status": "success", "url": url, "size": "123"},
        }
        mock_get.return_value = mock_resp

        result = enhancer.poll(tid)
        assert result.status == "succeeded"
        assert result.result_url == url

    @patch("app.tools.beautify.enhancer.requests.get")
    def test_poll_unknown_status_maps_to_failed(self, mock_get, enhancer):
        tid = "tid-abc"
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {
            tid: {"status": "error", "url": "", "size": ""},
        }
        mock_get.return_value = mock_resp

        result = enhancer.poll(tid)
        assert result.status == "failed"
        assert result.error is not None

    @patch("app.tools.beautify.enhancer.requests.get")
    def test_poll_new_status_maps_to_running(self, mock_get, enhancer):
        # 回归用例：bigjpg 在 submit 之后短时间内返回 "new"（排队中），
        # 必须当作 running 继续轮询，不能误判 failed。
        tid = "tid-new"
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {tid: {"status": "new", "url": "", "size": ""}}
        mock_get.return_value = mock_resp

        result = enhancer.poll(tid)
        assert result.status == "running"
        assert result.error is None

    @patch("app.tools.beautify.enhancer.requests.get")
    def test_poll_unknown_status_treated_as_running(self, mock_get, enhancer):
        # 未知 status（既不在 success 也不在 failed 集合）保守地继续轮询，
        # 由上层 5 分钟总超时兜底，避免误杀正在排队的任务。
        tid = "tid-foo"
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {tid: {"status": "weird-future-state", "url": ""}}
        mock_get.return_value = mock_resp

        result = enhancer.poll(tid)
        assert result.status == "running"

    @patch("app.tools.beautify.enhancer.requests.get")
    def test_poll_http_error_raises(self, mock_get, enhancer):
        mock_resp = MagicMock()
        mock_resp.ok = False
        mock_resp.status_code = 403
        mock_resp.text = "forbidden"
        mock_get.return_value = mock_resp

        with pytest.raises(RuntimeError) as exc_info:
            enhancer.poll("tid-abc")
        assert "HTTP 403" in str(exc_info.value)
