"""Behavioral checks for the dashboard JavaScript modules when Node is available."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def run_client_script():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is required for dashboard JavaScript behavior checks")
    frontend = Path(__file__).parents[1] / 'frontend/src/lib'
    imports = '\n'.join(
        f"import {{ {names} }} from {json.dumps((frontend / filename).as_uri())};"
        for filename, names in [
            ('markdown.js', 'renderInlineMarkdown, markdownToHtml'),
            ('stream.js', 'streamResponse'),
            ('monitor.js', 'streamOffset, needsDetailRefresh, filteredRequests'),
        ]
    )
    setup = imports + "\n" + """
        import assert from 'node:assert/strict';
        function target() { return () => {}; }
        function response(events, holdOpen = false, bytewise = false) {
            let cancelled = false;
            const body = new ReadableStream({
                start(controller) {
                    const bytes = new TextEncoder().encode(events);
                    if (bytewise) for (const byte of bytes) controller.enqueue(Uint8Array.of(byte));
                    else controller.enqueue(bytes);
                    if (!holdOpen) controller.close();
                },
                cancel() { cancelled = true; }
            });
            return {body, cancelled: () => cancelled};
        }
        function event(content, ending = '\\n') {
            return 'data: ' + JSON.stringify({choices: [{delta: {content}}]}) + ending + ending;
        }
    """

    def run(script):
        completed = subprocess.run(
            [node, "--input-type=module"],
            input=setup + script,
            text=True, capture_output=True, timeout=5,
        )
        assert completed.returncode == 0, completed.stderr

    return run


@pytest.mark.parametrize("ending", ["\n", "\r\n", "\r"])
def test_sse_framing_and_fragmented_unicode(run_client_script, ending):
    run_client_script("""
        const ending = ENDING;
        const result = await streamResponse(response(event('café 🌉', ending) +
            'data: [DONE]' + ending + ending, false, true), target());
        assert.equal(result, 'café 🌉');
    """.replace("ENDING", json.dumps(ending)))


def test_done_marker_finishes_without_waiting_for_eof(run_client_script):
    run_client_script("""
        const stream = response(event('done') + 'data: [DONE]\\n\\n', true);
        assert.equal(await streamResponse(stream, target()), 'done');
        assert.equal(stream.cancelled(), true);
    """)


@pytest.mark.parametrize("event", ["data: {broken}\\n\\n", "data: null\\n\\n"])
def test_invalid_stream_is_not_assistant_text(run_client_script, event):
    run_client_script("""
        await assert.rejects(streamResponse(response(EVENT), target()),
            error => error.type === 'stream_error' &&
                error.details.error.code === 'invalid_stream');
    """.replace("EVENT", json.dumps(event.replace("\\n", "\n"))))


def test_truncated_stream_does_not_commit_partial_success(run_client_script):
    run_client_script("""
        await assert.rejects(streamResponse(response(event('partial')), target()),
            error => error.details.error.code === 'incomplete_stream');
    """)


def test_markdown_links_and_code_keep_literal_content(run_client_script):
    run_client_script("""
        const html = renderInlineMarkdown('[query](https://example.test/*path*?a=1&b=2)');
        assert.equal(html, '<a href="https://example.test/*path*?a=1&amp;b=2"' +
            ' rel="noreferrer" target="_blank">query</a>');
        assert.equal(renderInlineMarkdown('`$&`'), '<code>$&amp;</code>');
        const unsafe = renderInlineMarkdown('[unsafe](javascript:alert(1))');
        assert.equal(unsafe.includes('href="#"'), true);
        assert.equal(markdownToHtml('```\\n<script>ignored</script>\\n```'),
            '<pre><code>&lt;script&gt;ignored&lt;/script&gt;</code></pre>');
    """)



def test_monitor_refreshes_finished_request_when_terminal_sse_was_missed(run_client_script):
    run_client_script("""
        const detail = {request_id: 'chatcmpl-00000001', is_active: true};
        assert.equal(needsDetailRefresh(detail, [{...detail}]), false);
        assert.equal(needsDetailRefresh(detail, [{...detail, is_active: false}]), true);
        assert.equal(needsDetailRefresh({...detail, is_active: false}, []), false);
        assert.equal(streamOffset('initial 🌉\\n'), 10);
    """)


def test_monitor_filters_status_model_and_id(run_client_script):
    run_client_script("""
        const requests = [{request_id: 'chatcmpl-00000001', model: 'codex/test', is_active: true}];
        for (const query of ['STREAMING', 'codex', '00000001'])
            assert.equal(filteredRequests(requests, query).length, 1);
        assert.equal(filteredRequests(requests, 'missing').length, 0);
    """)
