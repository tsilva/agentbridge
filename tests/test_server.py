"""
Unit tests for server functions and endpoint handlers.

These tests mock the Claude SDK and test server logic in isolation.

Usage:
- pytest tests/test_server.py -v
"""

import base64
import io
import json
import os
from importlib.metadata import version
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from agentbridge import __version__
from agentbridge.models import (
    ChatCompletionRequest,
    FunctionDefinition,
    ImageUrl,
    ImageUrlContent,
    Message,
    TextContent,
    Tool,
    resolve_model_request,
)
from agentbridge.server import (
    ClaudeResponse,
    _build_codex_command,
    _cleanup_codex_generated_thread,
    _codex_output_schema,
    _message_from_openrouter,
    _openrouter_client_kwargs,
    _openrouter_payload,
    _openrouter_to_dict,
    _parse_codex_json_lines,
    _parse_codex_run,
    _read_codex_generated_image,
    _resolve_codex_reasoning_effort,
    _usage_from_openrouter,
    app,
    build_tool_prompt,
    dashboard_state,
    extract_text_from_content,
    format_messages,
    format_multimodal_messages,
    main,
    parse_tool_response,
)


def _png_bytes() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (8, 10), "white").save(output, format="PNG")
    return output.getvalue()


class TestFormatMessages:
    """Tests for format_messages function."""

    def test_single_user_message(self):
        """Single user message formats correctly."""
        messages = [Message(role="user", content="Hello")]
        result = format_messages(messages)
        assert "User: Hello" in result

    def test_single_system_message(self):
        """System message appears at start."""
        messages = [
            Message(role="system", content="Be helpful"),
            Message(role="user", content="Hello"),
        ]
        result = format_messages(messages)
        assert result.startswith("System: Be helpful")
        assert "User: Hello" in result

    def test_conversation_format(self):
        """Multi-turn conversation formats correctly."""
        messages = [
            Message(role="user", content="Hi"),
            Message(role="assistant", content="Hello!"),
            Message(role="user", content="How are you?"),
        ]
        result = format_messages(messages)
        assert "User: Hi" in result
        assert "Assistant: Hello!" in result
        assert "User: How are you?" in result

    def test_empty_assistant_message_skipped(self):
        """Empty assistant messages are skipped."""
        messages = [
            Message(role="user", content="Hi"),
            Message(role="assistant", content=""),
            Message(role="user", content="Hello?"),
        ]
        result = format_messages(messages)
        # Should not have "Assistant:" for empty message
        assert result.count("Assistant:") == 0

    def test_none_content_handled(self):
        """None content (for tool calls) handled gracefully."""
        messages = [
            Message(role="assistant", content=None),
            Message(role="user", content="Continue"),
        ]
        result = format_messages(messages)
        # Should not crash, assistant line might be empty
        assert "User: Continue" in result


class TestExtractTextContent:
    """Tests for extract_text_from_content used by server formatting functions."""

    def test_single_text_part(self):
        """Single text part extracted."""
        content = [TextContent(type="text", text="Hello world")]
        result = extract_text_from_content(content)
        assert result == "Hello world"

    def test_multiple_text_parts(self):
        """Multiple text parts joined with space."""
        content = [
            TextContent(type="text", text="Hello"),
            TextContent(type="text", text="World"),
        ]
        result = extract_text_from_content(content)
        assert result == "Hello World"

    def test_mixed_content_text_and_image(self):
        """Mixed content extracts text and image placeholders."""
        content = [
            TextContent(type="text", text="Look at this:"),
            ImageUrlContent(
                type="image_url",
                image_url=ImageUrl(url="data:image/png;base64,abc"),
            ),
        ]
        result = extract_text_from_content(content)
        assert "Look at this:" in result
        assert "[image: base64 data]" in result

    def test_empty_content_list(self):
        """Empty content list returns empty string."""
        result = extract_text_from_content([])
        assert result == ""


class TestBuildToolPrompt:
    """Tests for build_tool_prompt function."""

    def test_single_tool_prompt(self):
        """Single tool creates appropriate prompt."""
        tools = [
            Tool(
                type="function",
                function=FunctionDefinition(
                    name="get_weather",
                    description="Get weather",
                    parameters={"type": "object", "properties": {"city": {"type": "string"}}},
                ),
            )
        ]
        result = build_tool_prompt(tools)
        assert "JSON object" in result
        assert '"type": "object"' in result

    def test_multiple_tools_prompt(self):
        """Multiple tools creates choice prompt."""
        tools = [
            Tool(
                type="function",
                function=FunctionDefinition(name="tool1"),
            ),
            Tool(
                type="function",
                function=FunctionDefinition(name="tool2"),
            ),
        ]
        result = build_tool_prompt(tools)
        assert "tool1" in result
        assert "tool2" in result
        assert "function" in result.lower()

    def test_tool_prompt_contains_schema(self):
        """Tool prompt includes function schema."""
        tools = [
            Tool(
                type="function",
                function=FunctionDefinition(
                    name="calculate",
                    parameters={
                        "type": "object",
                        "properties": {
                            "operation": {"type": "string"},
                            "numbers": {"type": "array"},
                        },
                    },
                ),
            )
        ]
        result = build_tool_prompt(tools)
        assert "operation" in result
        assert "numbers" in result


class TestParseToolResponse:
    """Tests for parse_tool_response function."""

    def test_parse_json_block(self):
        """Parse JSON in code block."""
        text = '```json\n{"city": "NYC"}\n```'
        tools = [
            Tool(
                type="function",
                function=FunctionDefinition(name="get_weather"),
            )
        ]
        remaining, tool_calls = parse_tool_response(text, tools)
        assert remaining == ""
        assert len(tool_calls) == 1
        assert tool_calls[0].function.name == "get_weather"
        args = json.loads(tool_calls[0].function.arguments)
        assert args["city"] == "NYC"

    def test_parse_raw_json(self):
        """Parse raw JSON object."""
        text = '{"value": 42}'
        tools = [
            Tool(
                type="function",
                function=FunctionDefinition(name="process"),
            )
        ]
        remaining, tool_calls = parse_tool_response(text, tools)
        assert len(tool_calls) == 1
        args = json.loads(tool_calls[0].function.arguments)
        assert args["value"] == 42

    def test_parse_multi_tool_response(self):
        """Parse response with function name for multiple tools."""
        text = '{"function": "tool2", "arguments": {"x": 1}}'
        tools = [
            Tool(type="function", function=FunctionDefinition(name="tool1")),
            Tool(type="function", function=FunctionDefinition(name="tool2")),
        ]
        remaining, tool_calls = parse_tool_response(text, tools)
        assert len(tool_calls) == 1
        assert tool_calls[0].function.name == "tool2"

    def test_no_json_returns_original_text(self):
        """No JSON returns original text."""
        text = "This is just plain text with no JSON."
        tools = [
            Tool(type="function", function=FunctionDefinition(name="test")),
        ]
        remaining, tool_calls = parse_tool_response(text, tools)
        assert remaining == text
        assert len(tool_calls) == 0

    def test_invalid_json_returns_text(self):
        """Invalid JSON returns original text."""
        text = "{invalid json here}"
        tools = [
            Tool(type="function", function=FunctionDefinition(name="test")),
        ]
        remaining, tool_calls = parse_tool_response(text, tools)
        # Should return original text since JSON is invalid
        assert remaining == text or len(tool_calls) == 0

    def test_tool_call_has_id(self):
        """Tool calls have unique IDs."""
        text = '{"key": "value"}'
        tools = [
            Tool(type="function", function=FunctionDefinition(name="test")),
        ]
        _, tool_calls = parse_tool_response(text, tools)
        assert tool_calls[0].id.startswith("call_")


class TestClaudeResponse:
    """Tests for ClaudeResponse container class."""

    def test_empty_response(self):
        """Empty response defaults."""
        resp = ClaudeResponse()
        assert resp.text == ""
        assert resp.tool_calls == []
        assert resp.usage is None
        assert not resp.has_tool_calls
        assert resp.finish_reason == "stop"

    def test_response_with_text(self):
        """Response with text."""
        resp = ClaudeResponse()
        resp.text = "Hello world"
        assert resp.text == "Hello world"
        assert resp.finish_reason == "stop"

    def test_response_with_tool_calls(self):
        """Response with tool calls."""
        from agentbridge.models import FunctionCall, ToolCall

        resp = ClaudeResponse()
        resp.tool_calls = [
            ToolCall(
                id="call_123",
                function=FunctionCall(name="test", arguments="{}"),
            )
        ]
        assert resp.has_tool_calls
        assert resp.finish_reason == "tool_calls"

    def test_get_usage_with_data(self):
        """get_usage returns OpenAI-format usage."""
        resp = ClaudeResponse()
        resp.usage = {"input_tokens": 100, "output_tokens": 50}
        usage = resp.get_usage()
        assert usage["prompt_tokens"] == 100
        assert usage["completion_tokens"] == 50
        assert usage["total_tokens"] == 150

    def test_get_usage_without_data(self):
        """get_usage returns zeros when no data."""
        resp = ClaudeResponse()
        usage = resp.get_usage()
        assert usage["prompt_tokens"] == 0
        assert usage["completion_tokens"] == 0
        assert usage["total_tokens"] == 0

    def test_get_usage_partial_data(self):
        """get_usage handles partial data."""
        resp = ClaudeResponse()
        resp.usage = {"input_tokens": 50}  # Missing output_tokens
        usage = resp.get_usage()
        assert usage["prompt_tokens"] == 50
        assert usage["completion_tokens"] == 0
        assert usage["total_tokens"] == 50


class TestCodexHelpers:
    """Tests for Codex CLI helper functions."""

    def test_build_codex_command_puts_global_options_before_exec(self):
        """Codex global approval policy must appear before the exec subcommand."""
        with patch("agentbridge.server._codex_binary", return_value="/bin/codex"):
            cmd = _build_codex_command(
                "gpt-5.4-mini",
                Path("/tmp/work"),
                Path("/tmp/work/out.txt"),
                [Path("/tmp/work/image.png")],
                "high",
            )

        assert cmd[:4] == ["/bin/codex", "-a", "never", "exec"]
        assert cmd[-1] == "-"
        model_arg_index = cmd.index("-m")
        assert cmd[model_arg_index + 1] == "gpt-5.4-mini"
        reasoning_arg_index = cmd.index("-c")
        assert cmd[reasoning_arg_index + 1] == 'model_reasoning_effort="high"'
        image_arg_index = cmd.index("--image")
        assert cmd[image_arg_index + 1] == "/tmp/work/image.png"

    def test_strict_image_command_isolates_config_and_enables_only_image_profile(self):
        with patch("agentbridge.server._codex_binary", return_value="/bin/codex"):
            cmd = _build_codex_command(
                "gpt-5.6-sol",
                Path("/tmp/work"),
                Path("/tmp/work/out.txt"),
                [Path("/tmp/work/reference.png")],
                "high",
                output_schema=Path("/tmp/work/schema.json"),
                strict=True,
                image_generation=True,
            )

        exec_index = cmd.index("exec")
        assert cmd.index("--disable") < exec_index
        assert cmd[exec_index + 1 : exec_index + 5] == [
            "--json",
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
        ]
        assert ["--disable", "shell_tool"] == cmd[3:5]
        assert "unified_exec" in cmd[:exec_index]
        assert "image_generation" in cmd[:exec_index]
        assert cmd[cmd.index("--output-schema") + 1] == "/tmp/work/schema.json"

    def test_parse_codex_run_extracts_trusted_thread_and_disallowed_tool_types(self):
        thread_id = "019feb8d-47c8-78e2-ba97-2d62a15b71c0"
        output = "\n".join(
            [
                json.dumps({"type": "thread.started", "thread_id": thread_id}),
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {"type": "command_execution", "command": "pwd"},
                    }
                ),
            ]
        )

        parsed = _parse_codex_run(output)

        assert parsed.thread_id == thread_id
        assert parsed.unexpected_tool_types == ("command_execution",)

    def test_codex_output_schema_extracts_openai_wrapper(self):
        schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}}
        assert _codex_output_schema(
            {
                "type": "json_schema",
                "json_schema": {"name": "answer", "strict": True, "schema": schema},
            }
        ) == schema

    def test_generated_image_is_read_only_from_exact_thread_directory(
        self, tmp_path, monkeypatch
    ):
        thread_id = "019feb8d-47c8-78e2-ba97-2d62a15b71c0"
        directory = tmp_path / "generated_images" / thread_id
        directory.mkdir(parents=True)
        expected = _png_bytes()
        (directory / "result.png").write_bytes(expected)
        monkeypatch.setenv("CODEX_HOME", str(tmp_path))

        assert _read_codex_generated_image(thread_id) == expected
        _cleanup_codex_generated_thread(thread_id)
        assert not directory.exists()

    def test_generated_image_size_is_checked_before_reading(self, tmp_path, monkeypatch):
        thread_id = "019feb8d-47c8-78e2-ba97-2d62a15b71c0"
        directory = tmp_path / "generated_images" / thread_id
        directory.mkdir(parents=True)
        (directory / "result.png").write_bytes(_png_bytes())
        monkeypatch.setenv("CODEX_HOME", str(tmp_path))

        with patch("agentbridge.server.MAX_IMAGE_OUTPUT_BYTES", 4), pytest.raises(
            RuntimeError, match="size limit"
        ):
            _read_codex_generated_image(thread_id)

    def test_parse_codex_json_lines_extracts_assistant_text_and_usage(self):
        """Codex JSONL parser handles assistant item and usage events."""
        output = "\n".join(
            [
                json.dumps({"type": "thread.started", "id": "abc"}),
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {
                            "type": "assistant_message",
                            "content": [{"type": "text", "text": "hello"}],
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "turn.completed",
                        "usage": {"input_tokens": 3, "output_tokens": 2},
                    }
                ),
            ]
        )

        text, usage = _parse_codex_json_lines(output)
        assert text == "hello"
        assert usage == {"input_tokens": 3, "output_tokens": 2}

    def test_parse_codex_json_lines_extracts_agent_message_text(self):
        """Codex CLI agent_message events are treated as assistant output."""
        output = "\n".join(
            [
                json.dumps({"type": "thread.started", "thread_id": "abc"}),
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {
                            "id": "item_0",
                            "type": "agent_message",
                            "text": "AGENTBRIDGE_CODEX_OK",
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "turn.completed",
                        "usage": {"input_tokens": 5, "output_tokens": 1},
                    }
                ),
            ]
        )

        text, usage = _parse_codex_json_lines(output)
        assert text == "AGENTBRIDGE_CODEX_OK"
        assert usage == {"input_tokens": 5, "output_tokens": 1}

    def test_gpt55_defaults_to_high_reasoning_effort(self):
        """gpt-5.5 Codex requests default to high reasoning."""
        request = ChatCompletionRequest(
            model="codex/gpt-5.5",
            messages=[Message(role="user", content="Hello")],
        )
        resolution = resolve_model_request(request.model)

        assert _resolve_codex_reasoning_effort(request, resolution) == "high"

    def test_gpt56_sol_defaults_to_high_reasoning_effort(self):
        """gpt-5.6-sol Codex requests default to high reasoning."""
        request = ChatCompletionRequest(
            model="codex/gpt-5.6-sol",
            messages=[Message(role="user", content="Hello")],
        )
        resolution = resolve_model_request(request.model)

        assert _resolve_codex_reasoning_effort(request, resolution) == "high"

    def test_request_reasoning_effort_overrides_gpt55_default(self):
        """Explicit reasoning_effort wins over the gpt-5.5 default."""
        request = ChatCompletionRequest(
            model="codex/gpt-5.5",
            messages=[Message(role="user", content="Hello")],
            reasoning_effort="medium",
        )
        resolution = resolve_model_request(request.model)

        assert _resolve_codex_reasoning_effort(request, resolution) == "medium"


class TestOpenRouterHelpers:
    """Tests for OpenRouter adapter helper functions."""

    def test_openrouter_client_kwargs_include_sdk_metadata(self, monkeypatch, tmp_path):
        """OpenRouter SDK client receives key and optional site metadata."""
        monkeypatch.setenv("AGENTBRIDGE_CONFIG_DIR", str(tmp_path))
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
        monkeypatch.setenv("OPENROUTER_SITE_URL", "https://agentbridge.test")
        monkeypatch.setenv("OPENROUTER_APP_NAME", "AgentBridge Test")

        kwargs = _openrouter_client_kwargs()

        assert kwargs == {
            "api_key": "sk-or-test",
            "timeout_ms": 120000,
            "http_referer": "https://agentbridge.test",
            "x_open_router_title": "AgentBridge Test",
        }

    def test_openrouter_payload_uses_backend_model(self):
        """OpenRouter payload strips the AgentBridge namespace."""
        request = ChatCompletionRequest(
            model="openrouter/anthropic/claude-sonnet-4",
            messages=[Message(role="user", content="Hello")],
            temperature=0.2,
        )

        payload = _openrouter_payload(
            request,
            "anthropic/claude-sonnet-4",
            stream=False,
        )

        assert payload["model"] == "anthropic/claude-sonnet-4"
        assert payload["stream"] is False
        assert payload["temperature"] == 0.2

    def test_openrouter_payload_normalizes_openai_only_fields(self):
        """OpenAI compatibility fields unsupported by the SDK are normalized."""
        request = ChatCompletionRequest(
            model="openrouter/openai/gpt-5",
            messages=[Message(role="user", content="Hello")],
            n=1,
            reasoning_effort="high",
        )

        payload = _openrouter_payload(request, "openai/gpt-5", stream=False)

        assert "n" not in payload
        assert "reasoning_effort" not in payload
        assert payload["reasoning"] == {"effort": "high"}

    def test_openrouter_sdk_object_normalizes_to_dict(self):
        """OpenRouter SDK Pydantic-like objects normalize before parsing."""

        class SDKResponse:
            def model_dump(self, **kwargs):
                assert kwargs["mode"] == "json"
                assert kwargs["exclude_none"] is True
                return {"choices": [{"message": {"content": "Hello"}}]}

        assert _openrouter_to_dict(SDKResponse()) == {
            "choices": [{"message": {"content": "Hello"}}],
        }

    def test_openrouter_message_and_usage_parse(self):
        """OpenRouter response JSON maps into local message and usage models."""
        data = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Hello back",
                    }
                }
            ],
            "usage": {
                "prompt_tokens": 3,
                "completion_tokens": 2,
                "total_tokens": 5,
            },
        }

        message = _message_from_openrouter(data)
        usage = _usage_from_openrouter(data)

        assert message.content == "Hello back"
        assert usage == {
            "prompt_tokens": 3,
            "completion_tokens": 2,
            "total_tokens": 5,
        }


class TestFormatMultimodalMessages:
    """Tests for format_multimodal_messages function."""

    def test_text_with_image(self):
        """Text and image content formatted correctly."""
        messages = [
            Message(
                role="user",
                content=[
                    TextContent(type="text", text="What's this?"),
                    ImageUrlContent(
                        type="image_url",
                        image_url=ImageUrl(url="data:image/png;base64,abc"),
                    ),
                ],
            )
        ]
        result = format_multimodal_messages(messages)
        assert len(result) == 2
        assert result[0]["type"] == "text"
        assert "User:" in result[0]["text"]
        assert result[1]["type"] == "image"

    def test_system_message_prepended(self):
        """System message prepended to content."""
        messages = [
            Message(role="system", content="Be helpful"),
            Message(
                role="user",
                content=[
                    TextContent(type="text", text="Hi"),
                    ImageUrlContent(
                        type="image_url",
                        image_url=ImageUrl(url="data:image/png;base64,abc"),
                    ),
                ],
            ),
        ]
        result = format_multimodal_messages(messages)
        assert result[0]["text"].startswith("System:")

    def test_multiple_images(self):
        """Multiple images in content."""
        messages = [
            Message(
                role="user",
                content=[
                    TextContent(type="text", text="Compare these:"),
                    ImageUrlContent(
                        type="image_url",
                        image_url=ImageUrl(url="data:image/png;base64,abc"),
                    ),
                    ImageUrlContent(
                        type="image_url",
                        image_url=ImageUrl(url="data:image/png;base64,xyz"),
                    ),
                ],
            )
        ]
        result = format_multimodal_messages(messages)
        image_blocks = [b for b in result if b["type"] == "image"]
        assert len(image_blocks) == 2


# Test the FastAPI app with TestClient
@pytest.fixture
def test_client(tmp_path, monkeypatch):
    """Create test client with mocked pool."""
    monkeypatch.setenv("LOG_DIR", str(tmp_path / "session-logs"))
    # We need to mock the pool to avoid connecting to real SDK
    with patch("agentbridge.server.pool") as mock_pool:
        # Create a mock that can be used with async context manager
        mock_client = AsyncMock()

        async def receive_response():
            if False:
                yield None

        mock_client.receive_response = receive_response
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
        yield TestClient(app, raise_server_exceptions=False)


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    def test_health_returns_ok(self, test_client):
        """Health endpoint returns status ok with version and pool info."""
        response = test_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["version"] == __version__ == version("agentbridge-py")


class TestCliConfiguration:
    """Tests for CLI ownership of runtime configuration."""

    def test_pool_size_environment_sets_worker_default(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AGENTBRIDGE_CONFIG_DIR", str(tmp_path))
        monkeypatch.setenv("POOL_SIZE", "4")
        monkeypatch.setattr("sys.argv", ["agentbridge"])

        with (
            patch("agentbridge.server._configure_logging"),
            patch("agentbridge.server._print_banner"),
            patch("uvicorn.run"),
        ):
            main()

        assert os.environ["POOL_SIZE"] == "4"

    def test_workers_flag_overrides_pool_size_environment(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AGENTBRIDGE_CONFIG_DIR", str(tmp_path))
        monkeypatch.setenv("POOL_SIZE", "4")
        monkeypatch.setattr("sys.argv", ["agentbridge", "--workers", "2"])

        with (
            patch("agentbridge.server._configure_logging"),
            patch("agentbridge.server._print_banner"),
            patch("uvicorn.run"),
        ):
            main()

        assert os.environ["POOL_SIZE"] == "2"


class TestModelsEndpoint:
    """Tests for /api/v1/models endpoint."""

    def test_models_returns_list(self, test_client):
        """Models endpoint returns list."""
        response = test_client.get("/api/v1/models")
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "list"
        assert len(data["data"]) > 0

    def test_models_have_openrouter_format(self, test_client):
        """Models include namespaced Claude Code, Codex, and OpenRouter slugs."""
        response = test_client.get("/api/v1/models")
        data = response.json()
        ids = {model["id"] for model in data["data"]}
        assert "codex/gpt-5.6-sol" in ids
        assert "codex/gpt-5.5" in ids
        assert "codex" not in ids
        assert any(model_id.startswith("claudecode/") for model_id in ids)
        assert any(model_id.startswith("codex/") for model_id in ids)
        assert any(model_id.startswith("openrouter/") for model_id in ids)
        for model in data["data"]:
            assert model["object"] == "model"


class TestCapabilitiesEndpoint:
    """Tests for the explicit Codex capability contract."""

    def test_reports_authenticated_strict_codex_features(self, test_client):
        probe = AsyncMock(
            side_effect=[
                (0, "codex-cli 0.144.1"),
                (0, "Logged in using ChatGPT"),
                (0, "image_generation stable true\n"),
                (
                    0,
                    "--disable --ephemeral --ignore-user-config --ignore-rules --sandbox "
                    "--output-schema",
                ),
            ]
        )
        with patch("agentbridge.server._codex_probe", new=probe):
            response = test_client.get("/api/v1/capabilities")

        assert response.status_code == 200
        codex = response.json()["codex"]
        assert codex == {
            "available": True,
            "authenticated": True,
            "cli_version": "0.144.1",
            "image_generation": True,
            "json_schema": True,
            "strict_profiles": True,
        }


class TestImageGenerationEndpoint:
    """Tests for the bounded native Codex image-generation route."""

    def test_returns_one_valid_base64_image(self, test_client):
        source = _png_bytes()
        generated = _png_bytes()
        call = AsyncMock(
            return_value=(generated, {"input_tokens": 11, "output_tokens": 7})
        )
        with (
            patch("agentbridge.server._call_codex_image", new=call),
            patch.object(
                dashboard_state,
                "request_started",
                wraps=dashboard_state.request_started,
            ) as started,
        ):
            response = test_client.post(
                "/api/v1/images",
                json={
                    "model": "codex/gpt-5.6-sol",
                    "prompt": "Make this look like a scanner capture without changing content.",
                    "input_references": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": "data:image/png;base64,"
                                + base64.b64encode(source).decode("ascii")
                            },
                        }
                    ],
                    "n": 1,
                    "store": False,
                },
            )

        assert response.status_code == 200
        body = response.json()
        assert base64.b64decode(body["data"][0]["b64_json"]) == generated
        assert body["usage"] == {
            "prompt_tokens": 11,
            "completion_tokens": 7,
            "total_tokens": 18,
        }
        assert body["usage_scope"] == "codex_orchestration_only"
        assert call.await_args.kwargs["source_data"] == source
        assert started.call_args.kwargs["messages"] == [
            {"role": "user", "content": "[image generation request]"}
        ]

    @pytest.mark.parametrize(
        ("model", "reference", "store"),
        [
            ("claudecode/sonnet", "data:image/png;base64,abc", False),
            ("codex/gpt-5.6-sol", "https://example.com/page.png", False),
            ("codex/gpt-5.6-sol", "data:image/png;base64,abc", True),
        ],
    )
    def test_rejects_non_codex_remote_or_persistent_requests(
        self, test_client, model, reference, store
    ):
        response = test_client.post(
            "/api/v1/images",
            json={
                "model": model,
                "prompt": "clean this page",
                "input_references": [
                    {"type": "image_url", "image_url": {"url": reference}}
                ],
                "store": store,
            },
        )

        assert response.status_code == 400


class TestChatCompletionsValidation:
    """Tests for /api/v1/chat/completions request validation."""

    def test_missing_model_error(self, test_client):
        """Missing model returns 400 error (custom validation error handler)."""
        response = test_client.post(
            "/api/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "Hi"}]},
        )
        assert response.status_code == 400  # Custom handler converts 422 → 400

    def test_missing_messages_error(self, test_client):
        """Missing messages returns 400 error (custom validation error handler)."""
        response = test_client.post(
            "/api/v1/chat/completions",
            json={"model": "claudecode/sonnet"},
        )
        assert response.status_code == 400  # Custom handler converts 422 → 400

    def test_invalid_model_error(self, test_client):
        """Invalid model returns OpenAI-format error."""
        response = test_client.post(
            "/api/v1/chat/completions",
            json={
                "model": "invalid-model-xyz",
                "messages": [{"role": "user", "content": "Hi"}],
            },
        )
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert data["error"]["type"] == "invalid_request_error"
        assert data["error"]["param"] == "model"

    def test_empty_messages_accepted(self, test_client):
        """Empty messages list is accepted by Pydantic but may fail later."""
        # Note: This tests Pydantic validation, not business logic
        test_client.post(
            "/api/v1/chat/completions",
            json={"model": "claudecode/sonnet", "messages": []},
        )
        # Empty messages might be accepted by validation
        # The actual error would come from the SDK call

    def test_extra_openrouter_params_accepted(self, test_client):
        """Extra OpenRouter/OpenAI parameters don't cause request rejection."""
        response = test_client.post(
            "/api/v1/chat/completions",
            json={
                "model": "claudecode/sonnet",
                "messages": [{"role": "user", "content": "Hi"}],
                "temperature": 0.5,
                "seed": 42,
                "n": 1,
                "user": "test-user",
                "response_format": {"type": "json_object"},
                "logprobs": True,
                "top_logprobs": 5,
            },
        )
        # Should not be 422 (validation error)
        assert response.status_code != 422

    def test_codex_multimodal_schema_request_uses_strict_profile_without_storage(
        self, test_client
    ):
        provider_response = ClaudeResponse()
        provider_response.text = '{"ok":true}'
        call = AsyncMock(return_value=provider_response)
        source = base64.b64encode(_png_bytes()).decode("ascii")
        schema = {
            "type": "object",
            "additionalProperties": False,
            "required": ["ok"],
            "properties": {"ok": {"type": "boolean"}},
        }

        with patch("agentbridge.server.call_codex_cli", new=call):
            response = test_client.post(
                "/api/v1/chat/completions",
                json={
                    "model": "codex/gpt-5.6-sol",
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "Inspect this untrusted page."},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{source}"
                                    },
                                },
                            ],
                        }
                    ],
                    "response_format": {
                        "type": "json_schema",
                        "json_schema": {
                            "name": "verdict",
                            "strict": True,
                            "schema": schema,
                        },
                    },
                    "store": False,
                },
            )

        assert response.status_code == 200
        assert call.await_args.kwargs["output_schema"] == schema
        assert call.await_args.kwargs["strict"] is True
        assert call.await_args.args[2].store is False


class TestNonStreamingDashboardLifecycle:
    """The endpoint owns dashboard state for non-streaming providers."""

    def test_success_completes_once(self, test_client):
        provider_response = ClaudeResponse()
        provider_response.text = "Hello"

        with (
            patch(
                "agentbridge.server.call_claude_sdk",
                new=AsyncMock(return_value=provider_response),
            ),
            patch.object(
                dashboard_state,
                "request_started",
                wraps=dashboard_state.request_started,
            ) as started,
            patch.object(
                dashboard_state,
                "request_completed",
                wraps=dashboard_state.request_completed,
            ) as completed,
            patch.object(
                dashboard_state,
                "request_errored",
                wraps=dashboard_state.request_errored,
            ) as errored,
            patch("agentbridge.server.SessionLogger.write"),
        ):
            response = test_client.post(
                "/api/v1/chat/completions",
                headers={"Authorization": "Bearer should-not-be-recorded"},
                json={
                    "model": "claudecode/sonnet",
                    "messages": [{"role": "user", "content": "Hi"}],
                },
            )

        assert response.status_code == 200
        started.assert_called_once()
        completed.assert_called_once_with(started.call_args.args[0])
        errored.assert_not_called()
        assert "api_key" not in started.call_args.kwargs

    def test_failure_errors_once(self, test_client):
        with (
            patch(
                "agentbridge.server.call_claude_sdk",
                new=AsyncMock(side_effect=RuntimeError("provider failed")),
            ),
            patch.object(
                dashboard_state,
                "request_started",
                wraps=dashboard_state.request_started,
            ) as started,
            patch.object(
                dashboard_state,
                "request_completed",
                wraps=dashboard_state.request_completed,
            ) as completed,
            patch.object(
                dashboard_state,
                "request_errored",
                wraps=dashboard_state.request_errored,
            ) as errored,
            patch("agentbridge.server.SessionLogger.write"),
        ):
            response = test_client.post(
                "/api/v1/chat/completions",
                json={
                    "model": "claudecode/sonnet",
                    "messages": [{"role": "user", "content": "Hi"}],
                },
            )

        assert response.status_code == 500
        completed.assert_not_called()
        errored.assert_called_once_with(started.call_args.args[0], "provider failed")


class TestErrorResponseFormat:
    """Tests for error response formatting."""

    def test_invalid_model_error_format(self, test_client):
        """Invalid model error has correct format."""
        response = test_client.post(
            "/api/v1/chat/completions",
            json={
                "model": "not-a-real-model",
                "messages": [{"role": "user", "content": "Hi"}],
            },
        )
        data = response.json()
        assert "error" in data
        assert "message" in data["error"]
        assert "type" in data["error"]
        assert data["error"]["code"] == "model_not_found"
