"""Behavioral checks for the dashboard's inline JavaScript when Node is available."""

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
    source = (Path(__file__).parents[1] / "agentbridge/templates/dashboard/chat.html").read_text()
    markdown = source[source.index("            function escapeHtml("):
                      source.index("            function renderAssistantMarkdown(")]
    streaming = source[source.index("            function parseSseEvent("):
                       source.index("            async function retryPreparedMessage(")]
    preparation = source[source.index("            async function buildUserContent("):
                         source.index("            function displayTextForMessage(")]
    send = source[source.index("            async function sendMessage("):
                  source.index("            async function checkHealth(")]
    page = (Path(__file__).parents[1] / "agentbridge/templates/dashboard/page.html").read_text()
    scripts = page.split("{% block scripts %}", 1)[1]
    monitor = scripts.split("<script>", 1)[1].split("</script>", 1)[0]
    setup = "const monitorScript = " + json.dumps(monitor) + ";\n" + """
        import assert from 'node:assert/strict';
        function appendAssistantDelta(target, delta) { target.dataset.rawMarkdown += delta; }
        function renderAssistantMarkdown(target, text) { target.dataset.rawMarkdown = text; }
        function target() {
            return {dataset: {rawMarkdown: ''}, classList: {contains: () => false}};
        }
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
            input=setup + markdown + streaming + preparation + send + script,
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



def test_attachment_reads_use_snapshot_and_preserve_next_draft(run_client_script):
    run_client_script("""
        const firstFile = {name: 'first.txt'};
        const nextFile = {name: 'next.txt'};
        let attachedFiles = [firstFile];
        let conversationMessages = [];
        let isSending = false;
        let captured;
        let finishRead;
        const promptEl = {value: 'first prompt'};
        const modelEl = {value: 'codex/gpt-6.1-sol'};
        function isTextFile() { return true; }
        function fileToText() { return new Promise(resolve => { finishRead = resolve; }); }
        function updateSendAvailability() {}
        function setStatus() {}
        function autosizePrompt() {}
        function saveDraft() {}
        function renderAttachedFiles() {}
        function displayTextForMessage(text) { return text; }
        function appendMessage() { return {}; }
        function appendError() { assert.fail('unexpected preparation error'); }
        async function submitPreparedMessage(payload) { captured = payload; }
        const pending = sendMessage();
        promptEl.value = 'next draft';
        attachedFiles = [nextFile];
        finishRead('first file contents');
        await pending;
        assert.equal(captured.messages[0].content[1].text.includes('first.txt'), true);
        assert.equal(captured.messages[0].content[1].text.includes('next.txt'), false);
        assert.equal(promptEl.value, 'next draft');
        assert.deepEqual(attachedFiles, [nextFile]);
        assert.equal(isSending, false);
    """)



_MONITOR_HARNESS = """
    function harness() {
        const handlers = {};
        const calls = [];
        let active = true;
        let livePanel = true;
        const id = 'chatcmpl-00000001';
        const row = {
            style: {}, textContent: id,
            getAttribute: () => id, scrollIntoView() {},
            classList: {contains: () => active, toggle() {}}
        };
        const detail = {id: 'detail', innerHTML: ''};
        const list = {
            addEventListener() {}, contains: () => true,
            querySelectorAll: selector => selector === '.request-row' ? [row] : [],
            querySelector: () => null
        };
        const filter = {value: '', addEventListener() {}};
        const document = {
            getElementById: id => id === 'request-list' ? list : filter,
            querySelector: () => livePanel ? {} : null,
            addEventListener() {},
            body: {addEventListener: (name, fn) => {handlers[name] = fn;}}
        };
        const window = {
            location: {search: '?request_id=' + id}, addEventListener() {},
            htmx: {ajax: (...args) => {calls.push(args);}}
        };
        function requestAnimationFrame(fn) { fn(); }
        eval(monitorScript);
        return {handlers, calls, detail,
            finish: () => {active = false;},
            rendered: () => {livePanel = false;}
        };
    }
"""


def test_monitor_refreshes_finished_request_when_terminal_sse_was_missed(run_client_script):
    run_client_script(_MONITOR_HARNESS + """
        const monitor = harness();
        assert.equal(monitor.calls.length, 1);
        monitor.finish();
        monitor.handlers['htmx:sseMessage']({target: {}});
        assert.equal(monitor.calls.length, 2);
        monitor.rendered();
        monitor.handlers['htmx:sseMessage']({target: {}});
        assert.equal(monitor.calls.length, 2);
    """)


def test_monitor_reports_missing_saved_request(run_client_script):
    run_client_script(_MONITOR_HARNESS + """
        const monitor = harness();
        monitor.handlers['htmx:responseError']({
            detail: {target: monitor.detail, xhr: {status: 404}}
        });
        assert.equal(monitor.detail.innerHTML.includes('Request not found'), true);
    """)
