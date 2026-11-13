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
├── config.py      # User configuration and log paths
└── static/dashboard/ # Packaged Svelte application

frontend/src/     # Svelte components, chat state, SSE and attachment helpers
```

## Validation

```bash
pnpm --dir frontend install --frozen-lockfile
pnpm --dir frontend check
pnpm --dir frontend test
pnpm --dir frontend build
uv run --frozen --extra test pytest -q
uv run --frozen --extra test ruff check agentbridge tests
uv lock --check
uv build
```

### Local native proxy administration

The approved local infrastructure source is restricted to Development `/proxy`, `AGENT_VAULT_PROXY_TOKEN` and
`AGENT_VAULT_CA_PRIVATE_KEY`. These are privileged proxy bootstrap values, not
AgentBridge application/provider keys. Only the trusted native proxy supervisor
may retrieve them. Never export this folder or inject its values into a tool,
model client, dev server or application job. Ordinary provider credentials remain
in their existing Agent Vault service bindings. The separate Development
`/recovery` folder contains encrypted administrative rollback state; it is never
an ordinary tool credential source. No automatic cross-profile fallback is allowed.

For the separate trusted native Vault proxy supervisor, follow
[`docs/local-vault-proxy.md`](docs/local-vault-proxy.md) and run its stdlib tests.
This administrative helper must never export upstream service keys to ordinary
clients, accept consumer scope overrides or cache the proxy's private CA locally.
Adding or testing it does not authorize a proxy/server restart, shared-session
renewal, credential rotation, app-default change or deployment.

## Dashboard audit

Use the project-level
[$agentbridge-dashboard-audit](.codex/skills/agentbridge-dashboard-audit/SKILL.md)
for hands-on local dashboard testing, reproducing and fixing requested bugs,
and verifying an authorized local reinstall/restart. It covers native in-app
Browser testing, deterministic fixtures, and regression verification.

## Release workflow

Use the project-level `$build-release` skill for version selection, release
validation, publishing, GitHub Release creation, and PyPI verification.
Normal release and validation builds run in GitHub Actions; use local compilation
only when explicitly requested. Validation dispatches never publish.

Use the native Codex Desktop in-app Browser for dashboard verification, and do
not disturb an existing development server.

## Shared release procedure

The project `build-release` skill composes `$release-workflow` from
`/Users/tsilva/.codex/skills/release-workflow/SKILL.md`.
Read both for release work; keep project commands, version policy, artifact
requirements, and approval gates in the project adapter.
