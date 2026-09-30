<p align="center">
  <img src="https://raw.githubusercontent.com/tsilva/agentbridge/main/logo.png" alt="AgentBridge" width="320" />
  <br />
  <!-- repo-tagline:start -->
  <strong>🌉 Claude, Codex, and OpenRouter through one API 🔌</strong>
  <!-- repo-tagline:end -->
</p>

<p align="center">
  <a href="https://github.com/tsilva/agentbridge/actions/workflows/ci.yml"><img src="https://github.com/tsilva/agentbridge/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI status" /></a>
  <a href="https://pypi.org/project/agentbridge-cli/"><img src="https://img.shields.io/pypi/v/agentbridge-cli" alt="PyPI version" /></a>
  <a href="https://github.com/tsilva/agentbridge/blob/main/pyproject.toml"><img src="https://img.shields.io/badge/python-%E2%89%A53.12-blue" alt="Python 3.12 or newer" /></a>
  <a href="https://github.com/tsilva/agentbridge/blob/main/LICENSE"><img src="https://img.shields.io/pypi/l/agentbridge-cli" alt="MIT license" /></a>
</p>

AgentBridge is a local API server that lets developers use Claude Code, Codex, and OpenRouter in chat apps built for OpenAI. Run it from the command line or the macOS menu-bar app, connect your chat client, and choose a backend with a provider-prefixed model ID.

It supports streaming and non-streaming responses, image and PDF inputs where the backend accepts them, native Codex image editing, strict JSON Schema output, OpenAI-style tool calls, a live dashboard, and local JSON session logs.

> **Legal notice:** agentbridge can use Claude Code SDK and Codex CLI access through your local subscriptions, and can forward requests to OpenRouter when configured. You are responsible for determining whether your use complies with each service's terms. Use it conservatively and at your own risk.

## Install

### Command line

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/):

```bash
uv tool install agentbridge-cli
agentbridge
```

If you installed an earlier release under the previous PyPI distribution name,
migrate once with:

```bash
uv tool uninstall agentbridge-py
uv tool install agentbridge-cli
```

The Python import and executable remain `agentbridge`.

Open the [dashboard](http://localhost:8082/dashboard), try the built-in [chat](http://localhost:8082/dashboard/chat), or use `http://localhost:8082/api/v1` as an OpenAI-compatible base URL.

Before sending requests, install [Claude Code](https://code.claude.com/docs/en/setup)
or [Codex CLI](https://learn.chatgpt.com/docs/codex/cli) for the backend you use.
Authenticate in another terminal if AgentBridge is already running:

```bash
claude auth login  # for claudecode/* models
codex login        # for codex/* models
```

For OpenRouter, start agentbridge once and add `OPENROUTER_API_KEY` to `~/.config/agentbridge/.env`.

### macOS menu-bar app

On an Apple silicon Mac running macOS 13+, download the arm64 DMG from the
[latest release](https://github.com/tsilva/agentbridge/releases/latest), drag
`AgentBridge.app` to Applications, and open it. The app is ad-hoc signed and
not Apple-notarized; macOS may require you to Control-click the app, choose
**Open**, and confirm on first launch. Intel Macs are not supported.

The menu-bar window starts and stops the server, shows health and activity,
opens the dashboard, and configures the port, worker count, and launch at login.
It bundles Python 3.12 and AgentBridge dependencies. Install and authenticate
provider tools separately as above; configuration and logs stay under
`~/.config/agentbridge/`.

### From source

```bash
git clone https://github.com/tsilva/agentbridge.git
cd agentbridge
uv sync --frozen --extra test
uv run agentbridge
```

To build the macOS app from the same checkout, install the Xcode Command Line
Tools and run:

```bash
scripts/build_macos_app.sh
open build/macos/arm64/AgentBridge-*.dmg
```

This requires an Apple silicon Mac running macOS 13+ and no Apple Developer
account. See [macOS development instructions](https://github.com/tsilva/agentbridge/blob/main/macos/README.md) for details.

## Usage

```bash
curl http://localhost:8082/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"claudecode/sonnet","messages":[{"role":"user","content":"Hello!"}]}'
```

Every request requires a model with one of these provider namespaces:

| Model format | Backend |
| --- | --- |
| `claudecode/<model>` | Claude Code: `opus`, `sonnet`, `haiku`, or a Claude slug containing one of those names |
| `codex/<model>` | Model ID passed directly to Codex CLI |
| `openrouter/<provider>/<model>` | Provider and model ID passed to the official OpenRouter Python SDK |

Codex chat defaults to low reasoning effort for `gpt-6-astra` and high for
`gpt-5.6-sol` and `gpt-5.5`; requests can override this. Astra image generation
also uses low reasoning effort.

With the OpenAI Python SDK installed, connect using any placeholder API key:

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8082/api/v1", api_key="not-needed")
response = client.chat.completions.create(
    model="codex/gpt-6-astra",
    reasoning_effort="high",
    messages=[{"role": "user", "content": "Hello from Codex!"}],
)
print(response.choices[0].message.content)
```

Codex can also edit one PNG, JPEG, or WebP reference through the image route.
The request returns one base64-encoded image without saving session logs.
Run this example from a repository checkout using the included sample image:

```bash
PAGE_DATA="$(base64 < tests/fixtures/ocr_test_document.png | tr -d '\n')"
curl http://localhost:8082/api/v1/images \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"codex/gpt-6-astra\",\"prompt\":\"Make this look like a scanner capture without changing any content.\",\"input_references\":[{\"type\":\"image_url\",\"image_url\":{\"url\":\"data:image/png;base64,$PAGE_DATA\"}}],\"n\":1,\"store\":false}"
```

`GET /api/v1/capabilities` reports whether the local Codex CLI is available,
authenticated, and supports the strict image and JSON-schema profiles.

## Commands

```bash
agentbridge                                             # start on 127.0.0.1:8082
agentbridge --port 8083                                  # choose another port
agentbridge --workers 3                                  # set Claude pool and Codex concurrency to 3
agentbridge --version                                    # print package and git version
uv run --frozen --extra test pytest -q                    # run tests
uv run --frozen --extra test ruff check agentbridge tests  # lint Python
swift test --package-path macos                          # test the macOS app
scripts/build_macos_app.sh                               # build a local signed app and DMG
uv lock --check                                         # verify the lockfile
uv build                                                # build wheel and source distribution
```

## Notes

- The server listens on `127.0.0.1:8082` by default and accepts any placeholder client API key.
- Public routes include `POST /api/v1/chat/completions`, `POST /api/v1/images`, `GET /api/v1/models`, `GET /api/v1/capabilities`, `GET /health`, `/dashboard`, and `/dashboard/chat`.
- `GET /health` includes safe operator status used by the menu-bar app: version, start time, uptime, configured workers, active requests, and pool state when initialized.
- Claude clients are created lazily, reused by model, and capped by the worker count. Claude sessions do not load filesystem settings and run with built-in tools disabled.
- Codex runs one ephemeral `codex exec` process per request in a temporary directory with read-only sandboxing, no approvals, and project rules ignored. Multimodal structured-output calls also ignore user config and disable execution and image-generation tools. Native image calls use the same strict profile, keep execution disabled, and enable the image-generation capability needed for the edit.
- Claude and Codex function calls are represented through prompted JSON; OpenRouter tool calls pass through its SDK. Session logs and extracted image or PDF attachments are saved under `~/.config/agentbridge/logs/sessions` by default.
- Streaming provider failures emit an OpenAI-shaped `error` object as an SSE `data` event before `[DONE]`; they are not returned as assistant message text.
- Set `store: false` on chat requests to suppress session-log artifacts. The native image route requires `store: false`, accepts data URLs only, validates both rasters, locates the result from the structured Codex thread ID, and removes that thread's generated-image directory after the request.

Configuration lives in `~/.config/agentbridge/.env`. Process environment
variables take precedence. CLI flags override the configured port and worker
count.

| Variable | Default or purpose |
| --- | --- |
| `PORT` | `8082` |
| `POOL_SIZE` | `1`; overridden by `--workers` |
| `CLAUDE_TIMEOUT` | `120` seconds |
| `CODEX_TIMEOUT`, `CODEX_IMAGE_TIMEOUT` | `600` seconds each |
| `OPENROUTER_TIMEOUT` | Falls back to `CLAUDE_TIMEOUT` (`120` seconds by default) |
| `MAX_IMAGE_INPUT_BYTES`, `MAX_IMAGE_OUTPUT_BYTES` | `67108864` (64 MiB) input, `33554432` (32 MiB) output |
| `MAX_IMAGE_PIXELS` | `40000000` (40 million pixels) |
| `AGENTBRIDGE_CONFIG_DIR` | Moves the configuration directory from `~/.config/agentbridge/` |
| `LOG_DIR` | Moves session logs from the configuration directory's `logs/sessions/` |
| `MAX_LOG_FILES` | Retains up to `1000` JSON session logs |
| `OPENROUTER_API_KEY` | Required for OpenRouter requests |
| `OPENROUTER_SITE_URL`, `OPENROUTER_APP_NAME` | Optional OpenRouter attribution; app name defaults to `agentbridge` |

## Publishing

Releases use the `Release` GitHub Actions workflow and PyPI Trusted Publishing
for the `agentbridge-cli` project. The publisher is scoped to owner `tsilva`,
repository `agentbridge`, workflow `release.yml`, and environment `pypi`; no
PyPI API token is required. GitHub Releases contain the Python distributions
plus an ad-hoc-signed arm64 macOS DMG and SHA-256 checksum. The DMG is not
Apple-notarized and requires no Apple Developer credentials. Releases
through `0.1.10` remain available under the previous `agentbridge-py`
distribution name.

## Architecture

![AgentBridge architecture diagram](https://raw.githubusercontent.com/tsilva/agentbridge/main/architecture.png)

## License

[MIT](https://github.com/tsilva/agentbridge/blob/main/LICENSE)
