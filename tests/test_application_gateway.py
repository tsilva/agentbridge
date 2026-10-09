"""Preserve application models, multimodal output, and gateway credential isolation."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from agentbridge import server


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENTBRIDGE_CONFIG_DIR", str(tmp_path))
    return TestClient(server.app)


def test_embeddings_strip_only_gateway_namespace(client):
    upstream = {"data": [{"embedding": [0.2, 0.5]}], "usage": {"prompt_tokens": 2}}
    forward = AsyncMock(return_value=upstream)
    with patch.object(server, "_openrouter_http_request", forward):
        response = client.post(
            "/api/v1/embeddings",
            json={
                "model": "openrouter/mistralai/mistral-embed-2312",
                "input": ["hello"],
                "dimensions": 2,
            },
        )
    assert response.status_code == 200
    assert response.json() == upstream
    assert forward.await_args.args == (
        "POST",
        "embeddings",
        {
            "model": "mistralai/mistral-embed-2312",
            "input": ["hello"],
            "dimensions": 2,
        },
    )


def test_non_embedding_provider_is_rejected_without_upstream_call(client):
    forward = AsyncMock()
    with patch.object(server, "_openrouter_http_request", forward):
        response = client.post(
            "/api/v1/embeddings",
            json={
                "model": "codex/gpt-6.1-sol",
                "input": "hello",
            },
        )
    assert response.status_code == 400
    forward.assert_not_awaited()


def test_openrouter_images_preserve_multiple_references_and_options(client):
    references = [{"type": "image_url", "image_url": {"url": "data:image/png;base64,YQ=="}}] * 2
    forward = AsyncMock(return_value={"data": [{"b64_json": "YQ=="}], "usage": {"cost": 0.1}})
    with patch.object(server, "_openrouter_http_request", forward):
        response = client.post(
            "/api/v1/images",
            json={
                "model": "openrouter/openai/gpt-image-2.5-flare",
                "prompt": "product photo",
                "input_references": references,
                "quality": "high",
                "store": False,
            },
        )
    assert response.status_code == 200
    payload = forward.await_args.args[2]
    assert payload["model"] == "openai/gpt-image-2.5-flare"
    assert payload["input_references"] == references
    assert payload["quality"] == "high"
    assert response.json()["usage"]["cost"] == 0.1


def test_chat_generated_images_and_pricing_survive_bridge(client):
    image = {"type": "image_url", "image_url": {"url": "data:image/png;base64,YQ=="}}
    upstream = {
        "id": "upstream",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "images": [image],
                }
            }
        ],
        "usage": {"prompt_tokens": 2, "completion_tokens": 3, "cost": 0.1},
    }
    forward = AsyncMock(return_value=upstream)
    with patch.object(server, "_openrouter_http_request", forward):
        response = client.post(
            "/api/v1/chat/completions",
            json={
                "model": "openrouter/google/gemini-3-pro-image-preview",
                "messages": [{"role": "user", "content": "logo"}],
                "modalities": ["image", "text"],
                "image_config": {"aspect_ratio": "1:1"},
            },
        )
    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["images"] == [image]
    assert response.json()["usage"]["cost"] == 0.1
    assert forward.await_args.args[2]["model"] == "google/gemini-3-pro-image-preview"


def test_metadata_does_not_allow_arbitrary_upstream_paths(client):
    forward = AsyncMock(return_value={"data": []})
    with patch.object(server, "_openrouter_http_request", forward):
        assert client.get("/api/v1/openrouter/models").status_code == 200
        assert client.get("/api/v1/openrouter/api_keys").status_code == 404
    assert forward.await_count == 1


async def test_forwarding_uses_gateway_credentials_and_transport(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "gateway-test-key")
    monkeypatch.setattr(server, "load_user_env", lambda **_kwargs: None)
    captured = []

    def handler(request):
        captured.append(request)
        return httpx.Response(200, json={"data": []})

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(server, "_openrouter_transport_kwargs", lambda: {"transport": transport})
    assert await server._openrouter_http_request("GET", "models") == {"data": []}
    assert str(captured[0].url) == "https://openrouter.ai/api/v1/models"
    assert captured[0].headers["Authorization"] == "Bearer gateway-test-key"


async def test_upstream_error_does_not_expose_response_body(monkeypatch):
    monkeypatch.setattr(server, "_openrouter_api_key", lambda: "gateway-test-key")
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            402,
            json={"error": {"message": "private prompt and credential"}},
        )
    )
    monkeypatch.setattr(server, "_openrouter_transport_kwargs", lambda: {"transport": transport})
    with pytest.raises(server.HTTPException) as caught:
        await server._openrouter_http_request("POST", "images", {"prompt": "private"})
    assert caught.value.status_code == 402
    assert "private" not in caught.value.detail


@pytest.mark.asyncio
async def test_extended_stream_retains_options_usage_and_gateway_credentials(monkeypatch):
    monkeypatch.setattr(server, "_openrouter_api_key", lambda: "gateway-owned")
    monkeypatch.setattr(server, "_openrouter_transport_kwargs", lambda: {})
    chunks = [
        {"choices": [{"delta": {"content": "hello"}}]},
        {"choices": [], "usage": {"cost": 0.07}},
    ]
    captured = []

    def upstream(request):
        import json

        captured.append(request)
        body = json.loads(request.content)
        assert body["model"] == "deepseek/deepseek-v4.1-flash"
        assert body["session_id"] == "session"
        assert body["max_completion_tokens"] == 2400
        assert request.headers["authorization"] == "Bearer gateway-owned"
        content = "".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks) + "data: [DONE]\n\n"
        return httpx.Response(200, text=content)

    original = httpx.AsyncClient
    monkeypatch.setattr(
        server.httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(upstream), **kwargs),
    )
    result = [
        chunk
        async for chunk in server._openrouter_stream_chunks(
            {
                "model": "deepseek/deepseek-v4.1-flash",
                "messages": [],
                "stream": True,
                "session_id": "session",
                "max_completion_tokens": 2400,
            }
        )
    ]
    assert result == chunks
    assert len(captured) == 1
