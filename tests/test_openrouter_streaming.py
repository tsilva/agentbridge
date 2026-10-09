"""OpenAI stream identity and payload preservation through the OpenRouter adapter."""

import asyncio
import json
from copy import deepcopy

import pytest

from agentbridge import server
from agentbridge.models import ChatCompletionRequest, Message


@pytest.mark.parametrize(
    "identity",
    [{"id": "gen-upstream", "created": 42}, {"id": None, "created": None}, {}],
    ids=["upstream-identity", "null-identity", "missing-identity"],
)
@pytest.mark.parametrize("tool_call", [False, True], ids=["text", "tool-call"])
async def test_openrouter_stream_identity_matches_header_and_log(
    monkeypatch,
    tmp_path,
    identity,
    tool_call,
):
    monkeypatch.setenv("AGENTBRIDGE_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    monkeypatch.setenv("OPENROUTER_DEFAULT_MODEL", "deepseek/deepseek-v4.1-flash")
    if tool_call:
        deltas = [
            {
                "tool_calls": [
                    {
                        "index": 0,
                        "id": "call-original",
                        "type": "function",
                        "function": {"name": "add_numbers", "arguments": '{"a":'},
                    }
                ]
            },
            {"tool_calls": [{"index": 0, "function": {"arguments": "17}"}}]},
        ]
        finish_reason = "tool_calls"
    else:
        deltas = [{"content": "café "}, {"content": "🌉"}]
        finish_reason = "stop"
    usage = {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5}
    upstream = [
        {
            **identity,
            "choices": [
                {"index": 0, "delta": delta, "finish_reason": finish_reason if i else None}
            ],
        }
        for i, delta in enumerate(deltas)
    ]
    upstream.append({**identity, "choices": [], "usage": usage})

    async def fake_stream(payload):
        assert payload["model"] == "deepseek/deepseek-v4.1-flash"
        assert payload["stream"] is True
        for chunk in deepcopy(upstream):
            yield chunk

    monkeypatch.setattr(server, "_openrouter_stream_chunks", fake_stream)
    response = await server.chat_completions(
        ChatCompletionRequest(
            model="openrouter/default",
            messages=[Message(role="user", content="Test stream")],
            stream=True,
            stream_options={"include_usage": True},
        )
    )
    request_id = response.headers["x-request-id"]
    frames = [frame async for frame in response.body_iterator]
    assert frames[-1] == "data: [DONE]\n\n"
    events = [json.loads(frame.removeprefix("data: ")) for frame in frames[:-1]]

    assert {event["id"] for event in events} == {request_id}
    assert isinstance(events[0]["created"], int)
    assert {event["created"] for event in events} == {events[0]["created"]}
    assert {event["model"] for event in events} == {"openrouter/default"}
    assert {event["object"] for event in events} == {"chat.completion.chunk"}
    assert events[0]["choices"][0]["delta"]["role"] == "assistant"
    assert events[-1]["choices"] == []
    assert events[-1]["usage"] == usage
    forwarded_choices = [event["choices"][0] for event in events[1:-1]]
    assert [choice["delta"] for choice in forwarded_choices] == deltas
    assert forwarded_choices[-1]["finish_reason"] == finish_reason

    log_path = tmp_path / f"{request_id}.json"
    for _ in range(100):
        try:
            saved = json.loads(log_path.read_text())
            break
        except (FileNotFoundError, json.JSONDecodeError):
            await asyncio.sleep(0.01)
    else:
        pytest.fail("Completed session log was not written")
    assert saved["request_id"] == request_id
    assert saved["finish_reason"] == finish_reason
    assert saved["error"] is None
    assert saved["usage"] == {"input_tokens": 3, "output_tokens": 2}
    assert saved["response"] == ("" if tool_call else "café 🌉")
    assert request_id not in {r["request_id"] for r in server.dashboard_state.get_active_requests()}
