"""Exercise the real SDK against a local forward proxy, without external calls."""

import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import httpx
import pytest

from agentbridge.server import _openrouter_client


@pytest.fixture
def isolated_openrouter(monkeypatch, tmp_path):
    for name in (
        "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
        "http_proxy", "https_proxy", "all_proxy", "no_proxy",
        "SSL_CERT_FILE", "SSL_CERT_DIR", "OPENROUTER_PROXY_URL", "OPENROUTER_CA_FILE",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AGENTBRIDGE_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("OPENROUTER_API_KEY", "placeholder")


@pytest.fixture
def denying_proxy():
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_CONNECT(self):
            requests.append((self.path, self.headers.get("Proxy-Authorization")))
            self.send_response(403)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *_args):
            pass

    proxy = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=proxy.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://session:proxy-password@127.0.0.1:{proxy.server_port}", requests
    finally:
        proxy.shutdown()
        proxy.server_close()
        thread.join(timeout=5)


@pytest.mark.parametrize("variable", ["OPENROUTER_PROXY_URL", "HTTPS_PROXY"])
@pytest.mark.parametrize("asynchronous", [True, False])
async def test_sdk_uses_authenticated_proxy_and_closes_on_failure(
    isolated_openrouter, denying_proxy, monkeypatch, variable, asynchronous,
):
    url, requests = denying_proxy
    monkeypatch.setenv(variable, url)
    if variable == "OPENROUTER_PROXY_URL":
        # Explicit provider settings take priority over standard bypass/proxy settings.
        monkeypatch.setenv("NO_PROXY", "*")
        monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
    with pytest.raises(httpx.ProxyError, match="403"):
        async with _openrouter_client() as sdk:
            sync_client = sdk.sdk_configuration.client
            async_client = sdk.sdk_configuration.async_client
            if asynchronous:
                await sdk.api_keys.get_current_key_metadata_async(
                    server_url="https://openrouter.invalid/api/v1", retries=None,
                )
            else:
                sdk.api_keys.get_current_key_metadata(
                    server_url="https://openrouter.invalid/api/v1", retries=None,
                )

    assert requests == [(
        "openrouter.invalid:443",
        "Basic " + base64.b64encode(b"session:proxy-password").decode(),
    )]
    assert sync_client.is_closed
    assert async_client.is_closed


@pytest.mark.parametrize("proxy", [
    "socks5://session:private-token@localhost:8080",
    "http://session:private-token@localhost:bad-port",
    "localhost:8080",
])
async def test_invalid_proxy_fails_without_exposing_credentials(
    isolated_openrouter, monkeypatch, proxy,
):
    monkeypatch.setenv("OPENROUTER_PROXY_URL", proxy)
    with pytest.raises(RuntimeError, match="OPENROUTER_PROXY_URL") as error:
        async with _openrouter_client():
            pytest.fail("An invalid proxy must fail before creating an SDK client")
    assert "private-token" not in str(error.value)


@pytest.mark.parametrize("exists", [True, False])
async def test_invalid_ca_fails_before_contacting_proxy(
    isolated_openrouter, denying_proxy, monkeypatch, tmp_path, exists,
):
    url, requests = denying_proxy
    ca_file = tmp_path / "proxy-ca.pem"
    if exists:
        ca_file.write_text("not a certificate")
    monkeypatch.setenv("OPENROUTER_PROXY_URL", url)
    monkeypatch.setenv("OPENROUTER_CA_FILE", str(ca_file))
    with pytest.raises(RuntimeError, match="OPENROUTER_CA_FILE"):
        async with _openrouter_client():
            pytest.fail("An invalid certificate must fail before sending a request")
    assert requests == []
