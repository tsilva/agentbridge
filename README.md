<div align="center">
  <img src="./logo.png" alt="AgentBridge" width="512" />

  **OpenAI-compatible routing for Claude Code, Codex, and OpenRouter — use your subscriptions anywhere.**
</div>

AgentBridge is a local API bridge for developers who want to connect OpenAI-compatible apps to Claude Code, Codex, or OpenRouter. Run one server, choose a backend with a namespaced model ID, and point existing Chat Completions clients at `http://localhost:8082/api/v1`.

It supports streaming and non-streaming responses, image and PDF inputs where the backend accepts them, native Codex image editing, strict JSON Schema output, OpenAI-style tool calls, a live dashboard, and local JSON session logs.

> **Legal notice:** agentbridge can use Claude Code SDK and Codex CLI access through your local subscriptions, and can forward requests to OpenRouter when configured. You are responsible for determining whether your use complies with each service's terms. Use it conservatively and at your own risk.

## Install

### macOS menu-bar app

On an Apple silicon Mac, download the arm64 DMG from the GitHub Release, drag
`AgentBridge.app` to Applications, and open it. The app is ad-hoc signed rather
than Apple-notarized, so on first launch macOS may require you to Control-click
the app, choose **Open**, and confirm. Intel Macs are not supported.

You can also build the app locally on macOS 13 or later. This requires
[uv](https://docs.astral.sh/uv/) and the Xcode Command Line Tools, but not an
Apple Developer account:

```bash
git clone https://github.com/tsilva/agentbridge.git
cd agentbridge
scripts/build_macos_app.sh
open "build/macos/$(uname -m)/AgentBridge-"*.dmg
```

The menu-bar window shows live server health and activity, starts and stops the
local server, opens the dashboard, and provides settings for the port, worker
count, and launch at login. See [`macos/README.md`](macos/README.md) for
development instructions.

The app contains its own Python 3.12 runtime and AgentBridge dependencies. It
does not bundle the Claude Code or Codex executables: installed provider tools
and their existing authentication state remain in the user account. Mutable
configuration and logs continue to live under `~/.config/agentbridge/`.

### Command line

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

Authenticate at least one backend before sending requests:

```bash
claude login    # for claudecode/* models
codex login     # for codex/* models
```

For OpenRouter, start agentbridge once and add `OPENROUTER_API_KEY` to `~/.config/agentbridge/.env`.

To work on the repository itself:

```bash
git clone https://github.com/tsilva/agentbridge.git
cd agentbridge
uv sync --extra test
uv run agentbridge
```

## Usage

```bash
curl http://localhost:8082/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"claudecode/sonnet","messages":[{"role":"user","content":"Hello!"}]}'
```

Every request requires one of these model namespaces:

- `claudecode/<model>` — `opus`, `sonnet`, `haiku`, or a namespaced Claude slug containing one of those names.
- `codex/<model>` — passed directly to Codex CLI. `gpt-5.6-sol` and `gpt-5.5` default to high reasoning effort unless the request overrides it.
- `openrouter/<provider>/<model>` — passed to the official OpenRouter Python SDK.

OpenAI SDKs may use any placeholder API key:

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8082/api/v1", api_key="not-needed")
response = client.chat.completions.create(
    model="codex/gpt-5.6-sol",
    reasoning_effort="high",
    messages=[{"role": "user", "content": "Hello from Codex!"}],
)
print(response.choices[0].message.content)
```

Codex can also edit one bounded PNG, JPEG, or WebP reference through the
purpose-built image route. The request is non-persistent and returns one base64
raster:

```bash
curl http://localhost:8082/api/v1/images \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"codex/gpt-5.6-sol\",\"prompt\":\"Make this look like a scanner capture without changing any content.\",\"input_references\":[{\"type\":\"image_url\",\"image_url\":{\"url\":\"data:image/png;base64,$PAGE_DATA\"}}],\"n\":1,\"store\":false}"
```

`GET /api/v1/capabilities` reports whether the local Codex CLI is available,
authenticated, and supports the strict image and JSON-schema profiles.

## Commands

```bash
agentbridge                                           # start on 127.0.0.1:8082
agentbridge --port 8083                               # choose another port
agentbridge --workers 3                               # set Claude pool and Codex concurrency to 3
agentbridge --version                                 # print package and git version
uv run --frozen --extra test pytest -q                # run tests
uv run --frozen --extra test ruff check agentbridge tests  # lint Python
swift test --package-path macos                    # test the macOS app
scripts/build_macos_app.sh                         # build a local signed app and DMG
uv lock --check                                       # verify the lockfile
uv build                                              # build wheel and source distribution
```

## Notes

- The CLI requires Python 3.12+; the macOS app bundles Python. At least one authenticated backend is required for provider requests.
- Public routes include `POST /api/v1/chat/completions`, `POST /api/v1/images`, `GET /api/v1/models`, `GET /api/v1/capabilities`, `GET /health`, `/dashboard`, and `/dashboard/chat`.
- `GET /health` includes safe operator status used by the menu-bar app: version, start time, uptime, configured workers, active requests, and pool state when initialized.
- `PORT`, `POOL_SIZE`, `CLAUDE_TIMEOUT`, `CODEX_TIMEOUT`, `CODEX_IMAGE_TIMEOUT`, and `OPENROUTER_TIMEOUT` control the server port, pool size, and provider timeouts. `--workers` overrides `POOL_SIZE`; Codex chat and native image generation default to 600-second timeouts, while Claude and OpenRouter default to 120 seconds.
- `MAX_IMAGE_INPUT_BYTES`, `MAX_IMAGE_OUTPUT_BYTES`, and `MAX_IMAGE_PIXELS` bound native image requests. Defaults are 64 MiB input, 32 MiB output, and 40 million pixels.
- `AGENTBRIDGE_CONFIG_DIR` moves the user configuration directory. `LOG_DIR` moves session logs, and `MAX_LOG_FILES` limits retained JSON logs.
- `OPENROUTER_API_KEY`, `OPENROUTER_SITE_URL`, and `OPENROUTER_APP_NAME` configure OpenRouter requests. Process environment variables take precedence over the user `.env` file.
- Claude clients are created lazily, reused by model, and capped by the worker count. Claude sessions do not load filesystem settings and run with built-in tools disabled.
- Codex runs one ephemeral `codex exec` process per request in a temporary directory with read-only sandboxing, no approvals, and project rules ignored. Multimodal structured-output calls also ignore user config and disable execution and image-generation tools. Native image calls use the same strict profile, keep execution disabled, and enable the image-generation capability needed for the edit.
- Claude and Codex function calls are represented through prompted JSON; OpenRouter tool calls pass through its SDK. Session logs and extracted image or PDF attachments are saved under `~/.config/agentbridge/logs/sessions` by default.
- Streaming provider failures emit an OpenAI-shaped `error` object as an SSE `data` event before `[DONE]`; they are not returned as assistant message text.
- Set `store: false` on chat requests to suppress session-log artifacts. The native image route requires `store: false`, accepts data URLs only, validates both rasters, locates the result from the structured Codex thread ID, and removes that thread's generated-image directory after the request.

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

![agentbridge architecture diagram](./architecture.png)

## License

[MIT](LICENSE)
