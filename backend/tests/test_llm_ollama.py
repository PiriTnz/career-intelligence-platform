"""
Unit tests for OllamaProvider.

All httpx calls are mocked — no running Ollama instance required.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch, call

import httpx
import pytest

from app.llm.ollama import OllamaProvider


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mock_response(*, json_data: dict, status: int = 200, raise_for_status=None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_data
    if raise_for_status:
        resp.raise_for_status.side_effect = raise_for_status
    else:
        resp.raise_for_status = MagicMock()
    return resp


def _mock_client(post_resp=None, get_resp=None, post_raises=None, get_raises=None) -> AsyncMock:
    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)

    if post_raises is not None:
        client.post = AsyncMock(side_effect=post_raises)
    elif post_resp is not None:
        client.post = AsyncMock(return_value=post_resp)

    if get_raises is not None:
        client.get = AsyncMock(side_effect=get_raises)
    elif get_resp is not None:
        client.get = AsyncMock(return_value=get_resp)

    return client


# ── Constructor / properties ──────────────────────────────────────────────────

class TestOllamaProviderProperties:
    def test_provider_name_is_ollama(self):
        p = OllamaProvider(base_url="http://localhost:11434", model="llama3")
        assert p.provider_name == "ollama"

    def test_model_property(self):
        p = OllamaProvider(base_url="http://localhost:11434", model="mistral")
        assert p.model == "mistral"

    def test_base_url_trailing_slash_stripped(self):
        p = OllamaProvider(base_url="http://localhost:11434/", model="llama3")
        assert not p._base_url.endswith("/")

    def test_custom_timeout_stored(self):
        p = OllamaProvider(base_url="http://localhost:11434", model="llama3", timeout=30.0)
        assert p._timeout == 30.0

    def test_custom_max_retries_stored(self):
        p = OllamaProvider(base_url="http://localhost:11434", model="llama3", max_retries=3)
        assert p._max_retries == 3


# ── generate() ───────────────────────────────────────────────────────────────

class TestGenerate:
    async def test_success_returns_text(self):
        resp = _mock_response(json_data={"response": "Great fit for this role."})
        mock_client = _mock_client(post_resp=resp)
        with patch("httpx.AsyncClient", return_value=mock_client):
            p = OllamaProvider(base_url="http://localhost:11434", model="llama3")
            result = await p.generate("Explain this score.", max_tokens=100)
        assert result == "Great fit for this role."

    async def test_strips_whitespace(self):
        resp = _mock_response(json_data={"response": "  Trimmed text.  "})
        mock_client = _mock_client(post_resp=resp)
        with patch("httpx.AsyncClient", return_value=mock_client):
            p = OllamaProvider(base_url="http://localhost:11434", model="llama3")
            result = await p.generate("prompt")
        assert result == "Trimmed text."

    async def test_empty_response_key_returns_empty(self):
        resp = _mock_response(json_data={})
        mock_client = _mock_client(post_resp=resp)
        with patch("httpx.AsyncClient", return_value=mock_client):
            p = OllamaProvider(base_url="http://localhost:11434", model="llama3")
            result = await p.generate("prompt")
        assert result == ""

    async def test_passes_num_predict(self):
        resp = _mock_response(json_data={"response": "ok"})
        mock_client = _mock_client(post_resp=resp)
        with patch("httpx.AsyncClient", return_value=mock_client):
            p = OllamaProvider(base_url="http://localhost:11434", model="llama3")
            await p.generate("prompt", max_tokens=42)
        call_kwargs = mock_client.post.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs.args[1]
        assert body["options"]["num_predict"] == 42

    async def test_passes_stream_false(self):
        resp = _mock_response(json_data={"response": "ok"})
        mock_client = _mock_client(post_resp=resp)
        with patch("httpx.AsyncClient", return_value=mock_client):
            p = OllamaProvider(base_url="http://localhost:11434", model="llama3")
            await p.generate("prompt")
        call_kwargs = mock_client.post.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs.args[1]
        assert body["stream"] is False

    async def test_timeout_returns_empty(self):
        mock_client = _mock_client(post_raises=httpx.TimeoutException("timeout"))
        with patch("httpx.AsyncClient", return_value=mock_client):
            p = OllamaProvider(base_url="http://localhost:11434", model="llama3", max_retries=1)
            result = await p.generate("prompt")
        assert result == ""

    async def test_retry_succeeds_on_second_attempt(self):
        resp_ok = _mock_response(json_data={"response": "retry worked"})
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(
            side_effect=[httpx.TimeoutException("t1"), resp_ok]
        )
        with patch("httpx.AsyncClient", return_value=mock_client):
            p = OllamaProvider(base_url="http://localhost:11434", model="llama3", max_retries=2)
            result = await p.generate("prompt")
        assert result == "retry worked"
        assert mock_client.post.call_count == 2

    async def test_all_retries_exhausted_returns_empty(self):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(
            side_effect=[
                httpx.TimeoutException("t1"),
                httpx.TimeoutException("t2"),
                httpx.TimeoutException("t3"),
            ]
        )
        with patch("httpx.AsyncClient", return_value=mock_client):
            p = OllamaProvider(base_url="http://localhost:11434", model="llama3", max_retries=3)
            result = await p.generate("prompt")
        assert result == ""
        assert mock_client.post.call_count == 3

    async def test_http_error_returns_empty_immediately(self):
        resp = _mock_response(
            json_data={},
            status=500,
            raise_for_status=httpx.HTTPStatusError(
                "server error", request=MagicMock(), response=MagicMock()
            ),
        )
        mock_client = _mock_client(post_resp=resp)
        with patch("httpx.AsyncClient", return_value=mock_client):
            p = OllamaProvider(base_url="http://localhost:11434", model="llama3", max_retries=3)
            result = await p.generate("prompt")
        assert result == ""
        assert mock_client.post.call_count == 1

    async def test_connect_error_retried(self):
        resp_ok = _mock_response(json_data={"response": "connected"})
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(
            side_effect=[httpx.ConnectError("connection refused"), resp_ok]
        )
        with patch("httpx.AsyncClient", return_value=mock_client):
            p = OllamaProvider(base_url="http://localhost:11434", model="llama3", max_retries=2)
            result = await p.generate("prompt")
        assert result == "connected"


# ── list_models() ─────────────────────────────────────────────────────────────

class TestListModels:
    async def test_returns_model_names(self):
        resp = _mock_response(json_data={
            "models": [{"name": "llama3"}, {"name": "mistral"}]
        })
        mock_client = _mock_client(get_resp=resp)
        with patch("httpx.AsyncClient", return_value=mock_client):
            p = OllamaProvider(base_url="http://localhost:11434", model="llama3")
            models = await p.list_models()
        assert models == ["llama3", "mistral"]

    async def test_non_200_returns_empty(self):
        resp = _mock_response(json_data={}, status=503)
        mock_client = _mock_client(get_resp=resp)
        with patch("httpx.AsyncClient", return_value=mock_client):
            p = OllamaProvider(base_url="http://localhost:11434", model="llama3")
            models = await p.list_models()
        assert models == []

    async def test_network_error_returns_empty(self):
        mock_client = _mock_client(get_raises=httpx.ConnectError("refused"))
        with patch("httpx.AsyncClient", return_value=mock_client):
            p = OllamaProvider(base_url="http://localhost:11434", model="llama3")
            models = await p.list_models()
        assert models == []

    async def test_empty_models_list(self):
        resp = _mock_response(json_data={"models": []})
        mock_client = _mock_client(get_resp=resp)
        with patch("httpx.AsyncClient", return_value=mock_client):
            p = OllamaProvider(base_url="http://localhost:11434", model="llama3")
            models = await p.list_models()
        assert models == []

    async def test_model_name_extracted_from_dict(self):
        resp = _mock_response(json_data={
            "models": [{"name": "llama3:latest", "size": 12345}]
        })
        mock_client = _mock_client(get_resp=resp)
        with patch("httpx.AsyncClient", return_value=mock_client):
            p = OllamaProvider(base_url="http://localhost:11434", model="llama3")
            models = await p.list_models()
        assert models == ["llama3:latest"]


# ── health_check() ────────────────────────────────────────────────────────────

class TestHealthCheck:
    async def test_true_when_model_present(self):
        resp = _mock_response(json_data={"models": [{"name": "llama3"}]})
        mock_client = _mock_client(get_resp=resp)
        with patch("httpx.AsyncClient", return_value=mock_client):
            p = OllamaProvider(base_url="http://localhost:11434", model="llama3")
            assert await p.health_check() is True

    async def test_true_when_model_tag_contains_model_name(self):
        resp = _mock_response(json_data={"models": [{"name": "llama3:latest"}]})
        mock_client = _mock_client(get_resp=resp)
        with patch("httpx.AsyncClient", return_value=mock_client):
            p = OllamaProvider(base_url="http://localhost:11434", model="llama3")
            assert await p.health_check() is True

    async def test_false_when_different_model_only(self):
        resp = _mock_response(json_data={"models": [{"name": "mistral"}]})
        mock_client = _mock_client(get_resp=resp)
        with patch("httpx.AsyncClient", return_value=mock_client):
            p = OllamaProvider(base_url="http://localhost:11434", model="llama3")
            assert await p.health_check() is False

    async def test_false_when_no_models_pulled(self):
        resp = _mock_response(json_data={"models": []})
        mock_client = _mock_client(get_resp=resp)
        with patch("httpx.AsyncClient", return_value=mock_client):
            p = OllamaProvider(base_url="http://localhost:11434", model="llama3")
            assert await p.health_check() is False

    async def test_false_on_network_error(self):
        mock_client = _mock_client(get_raises=httpx.ConnectError("refused"))
        with patch("httpx.AsyncClient", return_value=mock_client):
            p = OllamaProvider(base_url="http://localhost:11434", model="llama3")
            assert await p.health_check() is False

    async def test_false_when_ollama_returns_503(self):
        resp = _mock_response(json_data={}, status=503)
        mock_client = _mock_client(get_resp=resp)
        with patch("httpx.AsyncClient", return_value=mock_client):
            p = OllamaProvider(base_url="http://localhost:11434", model="llama3")
            assert await p.health_check() is False
