# agentbridge

Bridge OpenAI-compatible chat completions to Claude Code SDK, Codex CLI, and
OpenRouter.

## Source of truth

`README.md` owns the public product contract: installation, CLI usage, HTTP
routes, model formats, environment variables, examples, and publishing. Keep it
updated whenever those surfaces change instead of duplicating them here.

## Implementation contract

- Model IDs require an AgentBridge provider namespace: `claudecode/`, `codex/`,
  or `openrouter/`. The request model is mandatory.
- Both streaming and non-streaming `POST /api/v1/chat/completions` behavior are
  public. Preserve OpenAI-compatible response and error shapes.
- Claude clients are created lazily, reused by model, and capped by the worker
  count. Do not warm clients at startup.
- Claude sessions use `setting_sources=None`, the Claude Code preset system
  prompt, and `tools=[]` for isolated pure-chat operation.
- Codex runs ephemerally with read-only sandboxing, no approvals, and ignored
  project rules. OpenAI-style tool calls are emulated through prompted JSON.
- Session logs are displayed by the dashboard; saved attachments are persisted
  alongside them. Preserve their existing schema.

## Code map

```text
agentbridge/
├── server.py      # FastAPI app, provider adapters, CLI, session logging
├── pool.py        # Lazy Claude SDK client pool
├── models.py      # OpenAI schemas and provider model resolution
├── dashboard.py   # Dashboard routes and live request state
└── config.py      # User configuration and log paths
```

## Validation

```bash
uv run --frozen --extra test pytest -q
uv run --frozen --extra test ruff check agentbridge tests
uv lock --check
uv build
```

Use the native Codex Desktop in-app Browser for dashboard verification, and do
not disturb an existing development server.
