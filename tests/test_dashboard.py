"""
Unit tests for dashboard state tracking and routes.

Usage:
- pytest tests/test_dashboard.py -v
"""

import asyncio
import io
import json
import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from agentbridge.dashboard import (
    DashboardState,
    _ActiveRequest,
    _get_recent_logs,
    _parse_log_file,
    create_dashboard_router,
    templates,
)

# ---------------------------------------------------------------------------
# State tests
# ---------------------------------------------------------------------------

class TestActiveRequest:
    """Tests for _ActiveRequest dataclass."""

    def test_to_dict_fields(self):
        """to_dict returns all expected keys."""
        req = _ActiveRequest("req-1", "sonnet")
        d = req.to_dict()
        assert d["request_id"] == "req-1"
        assert d["model"] == "sonnet"
        assert isinstance(d["elapsed_s"], float)

    def test_elapsed_increases(self):
        """Elapsed time increases between calls."""
        import time
        req = _ActiveRequest("req-1", "sonnet")
        t1 = req.to_dict()["elapsed_s"]
        time.sleep(0.02)
        t2 = req.to_dict()["elapsed_s"]
        assert t2 > t1


class TestRequestLifecycle:
    """Tests for start, complete, error lifecycle."""

    def test_start_adds_request(self):
        """request_started adds to active list."""
        state = DashboardState()
        state.request_started("req-1", "opus")
        active = state.get_active_requests()
        assert len(active) == 1
        assert active[0]["request_id"] == "req-1"
        assert active[0]["model"] == "opus"

    def test_complete_removes_request(self):
        """request_completed removes from active list."""
        state = DashboardState()
        state.request_started("req-1", "opus")
        state.request_completed("req-1")
        assert state.get_active_requests() == []

    def test_error_removes_request(self):
        """request_errored removes from active list."""
        state = DashboardState()
        state.request_started("req-1", "opus")
        state.request_errored("req-1", "timeout")
        assert state.get_active_requests() == []

    def test_complete_unknown_request_no_error(self):
        """Completing an unknown request does not raise."""
        state = DashboardState()
        state.request_completed("nonexistent")  # should not raise

    def test_error_unknown_request_no_error(self):
        """Erroring an unknown request does not raise."""
        state = DashboardState()
        state.request_errored("nonexistent", "boom")  # should not raise

    def test_active_request_count_tracks_lifecycle(self):
        state = DashboardState()
        assert state.active_request_count() == 0

        state.request_started("req-1", "opus")
        state.request_started("req-2", "codex/gpt-5.6-sol")
        assert state.active_request_count() == 2

        state.request_completed("req-1")
        assert state.active_request_count() == 1


class TestMultipleActiveRequests:
    """Tests for concurrent request tracking."""

    def test_multiple_active(self):
        """Multiple requests can be active simultaneously."""
        state = DashboardState()
        state.request_started("req-1", "opus")
        state.request_started("req-2", "sonnet")
        state.request_started("req-3", "haiku")
        active = state.get_active_requests()
        assert len(active) == 3
        ids = {r["request_id"] for r in active}
        assert ids == {"req-1", "req-2", "req-3"}

    def test_completing_one_preserves_others(self):
        """Completing one request leaves others active."""
        state = DashboardState()
        state.request_started("req-1", "opus")
        state.request_started("req-2", "sonnet")
        state.request_completed("req-1")
        active = state.get_active_requests()
        assert len(active) == 1
        assert active[0]["request_id"] == "req-2"


class TestChunkHandling:
    """Tests for chunk handling."""

    def test_chunk_unknown_request_no_error(self):
        """Sending a chunk to an unknown request does not raise."""
        state = DashboardState()
        state.chunk_received("nonexistent", "data")  # should not raise


class TestSubscriptionFanOut:
    """Tests for subscriber queue fan-out."""

    async def test_single_subscriber_gets_chunk(self):
        """A subscriber receives chunk messages."""
        state = DashboardState()
        state.request_started("req-1", "opus")
        q = state.subscribe("req-1")
        assert q is not None

        state.chunk_received("req-1", "token")
        msg = q.get_nowait()
        assert msg == {"type": "chunk", "text": "token"}

    async def test_multiple_subscribers_get_same_chunks(self):
        """Multiple subscribers all receive the same chunk."""
        state = DashboardState()
        state.request_started("req-1", "opus")
        q1 = state.subscribe("req-1")
        q2 = state.subscribe("req-1")

        state.chunk_received("req-1", "hello")

        msg1 = q1.get_nowait()
        msg2 = q2.get_nowait()
        assert msg1 == {"type": "chunk", "text": "hello"}
        assert msg2 == {"type": "chunk", "text": "hello"}

    async def test_done_signal_to_subscribers(self):
        """Subscribers receive done signal on completion."""
        state = DashboardState()
        state.request_started("req-1", "opus")
        q = state.subscribe("req-1")

        state.request_completed("req-1")
        msg = q.get_nowait()
        assert msg == {"type": "done"}

    async def test_error_signal_to_subscribers(self):
        """Subscribers receive error signal on error."""
        state = DashboardState()
        state.request_started("req-1", "opus")
        q = state.subscribe("req-1")

        state.request_errored("req-1", "connection lost")
        msg = q.get_nowait()
        assert msg == {"type": "error", "error": "connection lost"}

    async def test_subscribe_unknown_request_returns_none(self):
        """Subscribing to an unknown request returns None."""
        state = DashboardState()
        result = state.subscribe("nonexistent")
        assert result is None


class TestUnsubscribe:
    """Tests for unsubscribe."""

    def test_unsubscribe_removes_queue(self):
        """Unsubscribed queue no longer receives chunks."""
        state = DashboardState()
        state.request_started("req-1", "opus")
        q = state.subscribe("req-1")

        state.unsubscribe("req-1", q)
        state.chunk_received("req-1", "after unsub")

        assert q.empty()

    def test_unsubscribe_unknown_request_no_error(self):
        """Unsubscribing from an unknown request does not raise."""
        state = DashboardState()
        q = asyncio.Queue()
        state.unsubscribe("nonexistent", q)  # should not raise

    def test_unsubscribe_unknown_queue_no_error(self):
        """Unsubscribing a queue that was never subscribed does not raise."""
        state = DashboardState()
        state.request_started("req-1", "opus")
        q = asyncio.Queue()
        state.unsubscribe("req-1", q)  # should not raise


# ---------------------------------------------------------------------------
# Route tests
# ---------------------------------------------------------------------------

def _make_app(state=None, pool_status_fn=None):
    """Create a minimal FastAPI app with the dashboard router mounted."""
    if state is None:
        state = DashboardState()
    if pool_status_fn is None:
        def pool_status_fn():
            return {"size": 3, "available": 2, "in_use": 1}

    app = FastAPI()
    router = create_dashboard_router(state, pool_status_fn)
    app.include_router(router)
    return app


SAMPLE_LOG = {
    "request_id": "chatcmpl-00abc123",
    "model": "sonnet",
    "api_key": None,
    "timestamp": "2026-02-14T10:00:00.000Z",
    "messages": [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there"},
    ],
    "parameters": {"stream": False, "temperature": None, "max_tokens": None},
    "response": "Hi there",
    "finish_reason": "stop",
    "timing": {"acquire_ms": 45, "query_ms": 1050, "duration_ms": 1100},
    "usage": {"input_tokens": 100, "output_tokens": 50},
    "error": None,
    "attachments": [],
}

SAMPLE_LOG_WITH_ERROR = {
    "request_id": "chatcmpl-e0000456",
    "model": "opus",
    "api_key": None,
    "timestamp": "2026-02-14T10:05:00.000Z",
    "messages": [{"role": "user", "content": "Do something"}],
    "parameters": {"stream": True, "temperature": None, "max_tokens": None},
    "response": "",
    "finish_reason": None,
    "timing": {"duration_ms": 2000},
    "usage": {},
    "error": "Timeout after 120s",
    "attachments": [],
}


class TestParseLogFile:
    """Tests for _parse_log_file."""

    def test_parses_valid_log(self, tmp_path):
        """Parses JSON log file with all expected fields."""
        log_path = tmp_path / "chatcmpl-00abc123.json"
        log_path.write_text(json.dumps(SAMPLE_LOG))

        result = _parse_log_file(log_path)
        assert result is not None
        assert result["request_id"] == "chatcmpl-00abc123"
        assert result["model"] == "sonnet"
        assert result["timestamp"] == "2026-02-14T10:00:00.000Z"
        assert result["timing"]["duration_ms"] == 1100
        assert result["timing"]["acquire_ms"] == 45
        assert result["timing"]["query_ms"] == 1050
        assert result["error"] is None
        assert len(result["messages"]) == 2
        assert result["response"] == "Hi there"

    def test_parses_error_log(self, tmp_path):
        """Parses log file with error."""
        log_path = tmp_path / "chatcmpl-e0000456.json"
        log_path.write_text(json.dumps(SAMPLE_LOG_WITH_ERROR))

        result = _parse_log_file(log_path)
        assert result is not None
        assert result["request_id"] == "chatcmpl-e0000456"
        assert result["error"] == "Timeout after 120s"

    def test_returns_none_for_missing_file(self, tmp_path):
        """Returns None if file does not exist."""
        result = _parse_log_file(tmp_path / "nonexistent.json")
        assert result is None

    def test_returns_none_for_garbage(self, tmp_path):
        """Returns None for a file with invalid JSON."""
        bad = tmp_path / "bad.json"
        bad.write_text("just some random text\nnothing useful here\n")
        result = _parse_log_file(bad)
        assert result is None


class TestGetRecentLogs:
    """Tests for _get_recent_logs."""

    def test_returns_empty_for_missing_dir(self, tmp_path, monkeypatch):
        """Returns empty list if log directory does not exist."""
        monkeypatch.setenv("LOG_DIR", str(tmp_path / "no_such_dir"))
        result = _get_recent_logs()
        assert result == []

    def test_returns_parsed_logs_newest_first(self, tmp_path, monkeypatch):
        """Returns logs sorted by mtime, newest first."""
        monkeypatch.setenv("LOG_DIR", str(tmp_path))

        older = {**SAMPLE_LOG, "request_id": "chatcmpl-01de7001"}
        newer = {**SAMPLE_LOG, "request_id": "chatcmpl-0e0e7001"}

        p1 = tmp_path / "chatcmpl-01de7001.json"
        p1.write_text(json.dumps(older))

        p2 = tmp_path / "chatcmpl-0e0e7001.json"
        p2.write_text(json.dumps(newer))

        # Ensure different mtimes
        os.utime(p1, (1000000, 1000000))
        os.utime(p2, (2000000, 2000000))

        result = _get_recent_logs(limit=10)
        assert len(result) == 2
        assert result[0]["request_id"] == "chatcmpl-0e0e7001"
        assert result[1]["request_id"] == "chatcmpl-01de7001"

    def test_respects_limit(self, tmp_path, monkeypatch):
        """Respects the limit parameter."""
        monkeypatch.setenv("LOG_DIR", str(tmp_path))

        for i in range(5):
            log = {**SAMPLE_LOG, "request_id": f"chatcmpl-{i:08x}"}
            p = tmp_path / f"chatcmpl-{i:08x}.json"
            p.write_text(json.dumps(log))

        result = _get_recent_logs(limit=2)
        assert len(result) == 2

    def test_invalid_recent_files_do_not_consume_the_result_limit(
        self, tmp_path, monkeypatch
    ):
        """Corrupt or non-session JSON files must not hide older valid sessions."""
        monkeypatch.setenv("LOG_DIR", str(tmp_path))
        for index in range(2):
            path = tmp_path / f"chatcmpl-{index:08x}.json"
            path.write_text(json.dumps({**SAMPLE_LOG, "request_id": path.stem}))
            os.utime(path, (100 + index, 100 + index))
        for index in range(3):
            path = tmp_path / f"invalid-{index}.json"
            path.write_text("not json")
            os.utime(path, (200 + index, 200 + index))

        result = _get_recent_logs(limit=2)

        assert len(result) == 2
        assert {item["request_id"] for item in result} == {
            "chatcmpl-00000000",
            "chatcmpl-00000001",
        }

    def test_zero_limit_returns_no_logs(self, tmp_path, monkeypatch):
        """A zero result limit must remain empty."""
        monkeypatch.setenv("LOG_DIR", str(tmp_path))
        (tmp_path / "chatcmpl-00000000.json").write_text(json.dumps(SAMPLE_LOG))

        assert _get_recent_logs(limit=0) == []


class TestDashboardPage:
    """Tests for GET /dashboard."""

    def test_returns_html_with_agentbridge(self):
        """Dashboard page returns HTML containing the AgentBridge brand."""
        app = _make_app()
        client = TestClient(app)
        resp = client.get("/dashboard")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "AgentBridge" in resp.text
        assert "request_id" in resp.text
        assert "loadSelectedDetail" in resp.text
        assert "/dashboard/request/" in resp.text
        assert 'href="/favicon.ico"' in resp.text
        assert 'href="/favicon.svg"' in resp.text
        assert 'href="/favicon-32.png"' in resp.text
        assert 'href="/favicon-16.png"' in resp.text
        assert 'href="/site.webmanifest"' in resp.text
        assert "MutationObserver" not in resp.text

    def test_dashboard_links_to_chat(self):
        """Dashboard page links to Chat."""
        app = _make_app()
        client = TestClient(app)
        resp = client.get("/dashboard")
        assert resp.status_code == 200
        assert 'class="nav-item" href="/dashboard/chat">Chat</a>' in resp.text

    def test_dashboard_interactions_have_accessible_semantics(self):
        """Filter and request controls remain keyboard and screen-reader friendly."""
        client = TestClient(_make_app())

        page = client.get("/dashboard")
        requests = templates.get_template("requests.html").render(
            requests=[
                {
                    **SAMPLE_LOG,
                    "is_active": False,
                    "duration_ms": 1100,
                    "input_tokens": 100,
                    "output_tokens": 50,
                }
            ]
        )

        assert 'aria-label="Filter requests"' in page.text
        assert '<button class="request-row' in requests
        assert 'type="button"' in requests
        assert 'class="filter-empty"' in requests
        assert "No matching requests" in requests

    def test_json_highlighter_uses_one_pass_over_plain_json(self):
        """Generated highlighting markup must never be processed as JSON again."""
        page = TestClient(_make_app()).get("/dashboard")

        assert "var jsonTokenPattern =" in page.text
        assert "return pretty.replace(jsonTokenPattern" in page.text
        assert ").replace(/\"(?:\\\\.|[^\"\\\\])*\"/g" not in page.text

    def test_back_navigation_restores_default_request(self):
        """Returning to the base dashboard must not leave stale request detail."""
        page = TestClient(_make_app()).get("/dashboard")

        assert "function loadDefaultRequest()" in page.text
        assert "else {\n                    loadDefaultRequest();\n                }" in page.text
        assert "markSelected(findRequestRow(selectedId), { scroll: false });" in page.text
        assert (
            "markSelected(findRequestRow(selectedId), { scroll: false });\n"
            "                    } else {\n"
            "                        loadDefaultRequest();"
        ) in page.text

    def test_serves_packaged_brand_assets(self):
        """Dashboard chrome assets are available from the installed package."""
        app = _make_app()
        client = TestClient(app)

        favicon = client.get("/dashboard/brand/favicon.ico")
        root_favicon = client.get("/favicon.ico")
        vector_favicon = client.get("/favicon.svg")
        favicon_32 = client.get("/favicon-32.png")
        manifest = client.get("/dashboard/brand/site.webmanifest")
        root_manifest = client.get("/site.webmanifest")

        assert favicon.status_code == 200
        assert favicon.headers["content-type"].startswith("image/x-icon")
        assert favicon.headers["cache-control"] == "public, max-age=86400"
        assert root_favicon.content == favicon.content
        assert vector_favicon.status_code == 200
        assert vector_favicon.headers["content-type"].startswith("image/svg+xml")
        assert b"AgentBridge" not in vector_favicon.content
        with Image.open(io.BytesIO(root_favicon.content)) as icon:
            assert icon.ico.sizes() == {(16, 16), (32, 32), (48, 48)}
        with Image.open(io.BytesIO(favicon_32.content)) as icon:
            assert icon.size == (32, 32)
        assert manifest.status_code == 200
        assert manifest.json()["theme_color"] == "#00483D"
        assert root_manifest.json() == manifest.json()
        assert client.get("/android-chrome-192.png").status_code == 200
        assert client.get("/apple-touch-icon.png").status_code == 200
        assert client.get("/dashboard/brand/not-allowed.svg").status_code == 404


class TestDashboardChatPage:
    """Tests for GET /dashboard/chat."""

    def test_returns_chat_html(self):
        """Chat page includes attachment and error-detail UI."""
        app = _make_app()
        client = TestClient(app)
        resp = client.get("/dashboard/chat")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "Send a test message" in resp.text
        assert "Drop files to attach" in resp.text
        assert "Copy details" in resp.text
        assert "Server error" in resp.text
        assert "model-badge" in resp.text
        assert "markdownToHtml" in resp.text
        assert "appendAssistantDelta" in resp.text
        assert 'rows="1"' in resp.text
        assert 'accept="image/*,application/pdf,text/plain,.txt"' in resp.text
        assert "is not an image, PDF, or TXT file" in resp.text
        assert "autosizePrompt" in resp.text
        assert "supportsStreaming" not in resp.text
        assert "Base URL" not in resp.text
        assert '<input id="base-url" type="hidden" value="/api/v1">' in resp.text
        assert "message-info" in resp.text
        assert "setMessageRequestId" in resp.text
        assert "sessionStorage.setItem(chatStateKey" in resp.text
        assert "restoreChatState" in resp.text
        assert "var renderedMessages = []" in resp.text
        assert 'modelEl.addEventListener("change", saveChatState)' in resp.text
        assert '"/dashboard?request_id=" + encodeURIComponent(requestId)' in resp.text
        assert 'class="main-nav"' in resp.text
        assert 'class="nav-item" href="/dashboard">Monitor</a>' in resp.text
        assert 'class="nav-item active" href="/dashboard/chat">Chat</a>' in resp.text
        assert '<option value="codex/gpt-5.6-sol">codex/gpt-5.6-sol</option>' in resp.text
        assert 'if (e.key !== "Enter" || e.isComposing) return;' in resp.text
        assert "if (e.altKey) return;" in resp.text
        assert "e.preventDefault();" in resp.text
        assert 'aria-label="Send message"' in resp.text
        assert '<button id="send" class="primary" type="button">Send</button>' not in resp.text
        assert "typing-indicator" in resp.text
        assert "Assistant is typing" in resp.text
        assert 'loading: true' in resp.text
        assert "loadModels" not in resp.text
        assert "responseText" not in resp.text
        assert "stream: true" in resp.text
        assert "var conversationMessages = []" in resp.text
        assert "messages: conversationMessages.concat([userMessage])" in resp.text
        assert (
            'conversationMessages.push({ role: "assistant", content: streamedText })'
            in resp.text
        )
        assert "Copy cURL" not in resp.text
        assert 'id="stream"' not in resp.text

    def test_hidden_file_picker_is_not_a_duplicate_tab_stop(self):
        """Only the visible attach button should be keyboard focusable."""
        resp = TestClient(_make_app()).get("/dashboard/chat")

        assert (
            '<input id="file-input" class="hidden-input" type="file" '
            'tabindex="-1" aria-hidden="true"'
        ) in resp.text

    def test_composer_exposes_only_available_and_named_actions(self):
        """Composer actions communicate whether they can run and what they remove."""
        resp = TestClient(_make_app()).get("/dashboard/chat")

        assert 'id="send" class="primary" type="button" disabled' in resp.text
        assert "function updateSendAvailability()" in resp.text
        assert 'remove.setAttribute("aria-label", "Remove " + fileName)' in resp.text

    def test_retry_replays_the_prepared_request(self):
        """Retry must retain the failed payload after the composer is cleared."""
        resp = TestClient(_make_app()).get("/dashboard/chat")

        assert (
            "function appendError(status, statusText, body, requestId, retryAction, options)"
            in resp.text
        )
        assert "async function submitPreparedMessage(payload, userMessage, userTarget)" in resp.text
        assert 'retry.addEventListener("click", sendMessage)' not in resp.text
        assert "if (chunk.error)" in resp.text
        assert 'error.type = "stream_error"' in resp.text
        assert 'if (e.type === "stream_error") throw e;' in resp.text
        assert "var summary = status ? String(status)" in resp.text

    def test_discarded_assistant_is_removed_from_persisted_chat_state(self):
        """A failed loading message must not return as a blank message on reload."""
        resp = TestClient(_make_app()).get("/dashboard/chat")

        assert "function removeRenderedMessage(article)" in resp.text
        assert "renderedMessages.splice(index, 1);" in resp.text
        assert "removeRenderedMessage(article);" in resp.text
        assert 'role: "error"' in resp.text
        assert 'if (message.role === "error")' in resp.text


class TestDashboardPool:
    """Tests for GET /dashboard/pool."""

    def test_returns_html_with_pool_dot(self):
        """Pool endpoint returns HTML with 'pool-dot'."""
        app = _make_app()
        client = TestClient(app)
        resp = client.get("/dashboard/pool")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "pool-dot" in resp.text

    def test_lazy_empty_pool_shows_capacity_available(self):
        """A lazily initialized empty pool still has request capacity."""
        app = _make_app(
            pool_status_fn=lambda: {"size": 1, "available": 0, "in_use": 0}
        )
        client = TestClient(app)
        resp = client.get("/dashboard/pool")
        assert resp.status_code == 200
        assert "Healthy" in resp.text
        assert "1/1 capacity" in resp.text
        assert "Busy" not in resp.text

    def test_pool_at_capacity_shows_busy(self):
        """Pool status reports busy only when all worker capacity is in use."""
        app = _make_app(
            pool_status_fn=lambda: {"size": 1, "available": 0, "in_use": 1}
        )
        client = TestClient(app)
        resp = client.get("/dashboard/pool")
        assert resp.status_code == 200
        assert "Busy" in resp.text
        assert "0/1 capacity" in resp.text


class TestDashboardRequests:
    """Tests for GET /dashboard/requests."""

    def test_returns_sse_content_type(self):
        """Requests endpoint returns SSE content-type."""
        import asyncio
        from unittest.mock import AsyncMock, MagicMock

        from fastapi.responses import StreamingResponse

        state = DashboardState()
        def pool_fn():
            return {"size": 3, "available": 2, "in_use": 1}

        router = create_dashboard_router(state, pool_fn)

        handler = None
        for route in router.routes:
            if hasattr(route, "path") and route.path == "/dashboard/requests":
                handler = route.endpoint
                break

        assert handler is not None, "Could not find /dashboard/requests route"

        mock_request = MagicMock()
        mock_request.is_disconnected = AsyncMock(return_value=False)

        loop = asyncio.new_event_loop()
        try:
            resp = loop.run_until_complete(handler(mock_request))
        finally:
            loop.close()
        assert isinstance(resp, StreamingResponse)
        assert resp.media_type == "text/event-stream"

    def test_sse_contains_active_and_completed(self, tmp_path, monkeypatch):
        """SSE stream renders both active and completed requests."""
        import asyncio
        from unittest.mock import AsyncMock, MagicMock


        monkeypatch.setenv("LOG_DIR", str(tmp_path))
        log = {**SAMPLE_LOG, "request_id": "chatcmpl-d0000001"}
        log_path = tmp_path / "chatcmpl-d0000001.json"
        log_path.write_text(json.dumps(log))

        state = DashboardState()
        state.request_started("chatcmpl-11000001", "sonnet")
        def pool_fn():
            return {"size": 3, "available": 2, "in_use": 1}

        router = create_dashboard_router(state, pool_fn)

        handler = None
        for route in router.routes:
            if hasattr(route, "path") and route.path == "/dashboard/requests":
                handler = route.endpoint
                break

        mock_request = MagicMock()
        mock_request.is_disconnected = AsyncMock(side_effect=[False, True])

        loop = asyncio.new_event_loop()
        try:
            resp = loop.run_until_complete(handler(mock_request))
            chunks = []
            async def collect():
                async for chunk in resp.body_iterator:
                    chunks.append(chunk)
                    break
            loop.run_until_complete(collect())
        finally:
            loop.close()

        content = "".join(chunks)
        assert "chatcmpl-11000001" in content or "11000001" in content
        assert "chatcmpl-d0000001" in content or "d0000001" in content
        assert "request-row-active" in content


@pytest.mark.parametrize(
    "path",
    [
        "/dashboard/request/not-valid",
        "/dashboard/log/not-valid",
        "/dashboard/attachment/not-valid/file.txt",
        "/dashboard/stream/not-valid",
    ],
)
def test_dashboard_routes_reject_invalid_request_ids(path):
    """Every request-specific dashboard route applies the same validation."""
    client = TestClient(_make_app())
    response = client.get(path)
    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid request ID"}


class TestDashboardRequestDetail:
    """Tests for GET /dashboard/request/{request_id}."""

    def test_active_request_shows_live_stream(self):
        """Active request detail shows 'Live Stream'."""
        state = DashboardState()
        state.request_started("chatcmpl-11111111", "sonnet")
        app = _make_app(state=state)
        client = TestClient(app)
        resp = client.get("/dashboard/request/chatcmpl-11111111")
        assert resp.status_code == 200
        assert "Live Stream" in resp.text

    def test_log_file_request_shows_detail(self, tmp_path, monkeypatch):
        """Completed request detail is rendered from log file."""
        monkeypatch.setenv("LOG_DIR", str(tmp_path))
        log_path = tmp_path / "chatcmpl-00abc123.json"
        log_path.write_text(json.dumps(SAMPLE_LOG))

        app = _make_app()
        client = TestClient(app)
        resp = client.get("/dashboard/request/chatcmpl-00abc123")
        assert resp.status_code == 200
        assert "chatcmpl-00abc123" in resp.text

    def test_unknown_request_returns_404(self, tmp_path, monkeypatch):
        """Unknown request returns 404."""
        monkeypatch.setenv("LOG_DIR", str(tmp_path))
        app = _make_app()
        client = TestClient(app)
        resp = client.get("/dashboard/request/chatcmpl-deadbeef")
        assert resp.status_code == 404

    def test_null_timing_and_usage_render_as_missing_metadata(
        self, tmp_path, monkeypatch
    ):
        """Partially written logs must not crash the request detail route."""
        monkeypatch.setenv("LOG_DIR", str(tmp_path))
        log = {
            **SAMPLE_LOG,
            "request_id": "chatcmpl-0badcafe",
            "timing": None,
            "usage": None,
        }
        (tmp_path / "chatcmpl-0badcafe.json").write_text(json.dumps(log))

        resp = TestClient(_make_app()).get("/dashboard/request/chatcmpl-0badcafe")

        assert resp.status_code == 200
        assert "chatcmpl-0badcafe" in resp.text


class TestDashboardStream:
    """Tests for GET /dashboard/stream/{request_id}."""

    def test_stream_inactive_request_returns_404(self):
        """Streaming an inactive request returns 404."""
        app = _make_app()
        client = TestClient(app)
        resp = client.get("/dashboard/stream/chatcmpl-00000000")
        assert resp.status_code == 404
