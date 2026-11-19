"""Verify AgentBridge's provider settings stay outside real SDK child environments."""

import asyncio
import json
import os
import sys

import certifi
from claude_agent_sdk._internal.transport.subprocess_cli import SubprocessCLITransport

from agentbridge import server
from agentbridge.pool import make_options


async def test_server_keeps_openrouter_settings_out_of_native_children(monkeypatch, tmp_path):
    # Scope app state to the test so it cannot alter another TestClient.
    from starlette.datastructures import State

    monkeypatch.setattr(server.app, "state", State())
    monkeypatch.setenv("AGENTBRIDGE_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("CLAUDE_AGENT_SDK_SKIP_VERSION_CHECK", raising=False)

    key, proxy = "fake-provider-key", "http://session:fake-proxy-password@127.0.0.1:1"
    names = ("OPENROUTER_API_KEY", "OPENROUTER_PROXY_URL", "OPENROUTER_CA_FILE")
    (tmp_path / ".env").write_text(
        "OPENROUTER_API_KEY=fake-file-default\n"
        "OPENROUTER_PROXY_URL=http://127.0.0.1:2\n"
        f"OPENROUTER_CA_FILE={certifi.where()}\n"
    )
    monkeypatch.setenv(names[0], key)
    monkeypatch.setenv(names[1], proxy)
    monkeypatch.delenv(names[2], raising=False)
    monkeypatch.setenv("AGENTBRIDGE_CHILD_TEST_SETTING", "ordinary")
    record = tmp_path / "child-probes.jsonl"
    cli = tmp_path / "synthetic-cli"
    cli.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "kind = 'claude-version' if sys.argv[1:] == ['-v'] else "
        "('codex' if sys.argv[1:] == ['--version'] else 'claude-session')\n"
        f"with open({str(record)!r}, 'a', encoding='utf-8') as report:\n"
        f"    json.dump([kind, [name for name in {names!r} if name in os.environ], "
        "os.environ.get('AGENTBRIDGE_CHILD_TEST_SETTING')], report)\n"
        "    report.write('\\n')\n"
        "print('2.2.0' if kind != 'claude-session' else '{\"type\": \"system\"}', flush=True)\n"
    )
    cli.chmod(0o700)
    monkeypatch.setenv("CODEX_BIN", str(cli))
    monkeypatch.setenv("CLAUDE_BIN", str(cli))

    async with server.lifespan(server.app):
        assert server._openrouter_api_key() == key
        transport = server._openrouter_transport_kwargs()
        assert transport["proxy"] == proxy
        assert transport["verify"].get_ca_certs()
        assert all(name not in os.environ for name in names)
        assert await server._codex_probe("--version") == (0, "2.2.0\n")
        claude = SubprocessCLITransport("", make_options("sonnet"))
        await claude.connect()
        try:
            messages = claude.read_messages()
            assert await asyncio.wait_for(anext(messages), timeout=5) == {"type": "system"}
            await messages.aclose()
        finally:
            await claude.close()

    assert [json.loads(line) for line in record.read_text().splitlines()] == [
        ["codex", [], "ordinary"],
        ["claude-version", [], "ordinary"],
        ["claude-session", [], "ordinary"],
    ]
