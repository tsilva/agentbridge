# Local installation and validation

Read this when reinstall/restart is requested or source and installed behavior
diverge. Discover paths from the actual running process. A uv-managed CLI and a
packaged menu-bar application can use different runtimes.

## Discover and preserve

1. Record the dashboard URL, health start time/version, listening PID, command,
   supervisor configuration, and log locations. Resolve the launcher and its
   Python environment; locate the imported `agentbridge` package and distribution
   metadata. Do not print secrets from process environments or configuration.
2. For a uv tool, inspect its registered environment and Python executable. On
   macOS, inspect the actual launchd job/plist when launchd owns the process.
   Do not assume a historical label such as `io.parsefood.agentbridge`.
3. Preserve the installed artifact or package/metadata backup needed for rollback.
   Build the checkout with `uv build`; identify the exact resulting wheel and
   compare its templates/assets to source before installation.
4. Confirm restart authorization from the current request or existing session.
   Check active requests immediately before maintenance. Wait for user work to
   finish; do not cancel unrelated requests just to speed up an audit. Preserve
   service configuration, logs, attachments, and user preferences.

## Install and restart the discovered target

For an existing uv-tool environment with compatible locked dependencies, use
the discovered interpreter and exact wheel path:

```bash
uv pip install --python <tool-python> --no-deps --reinstall <built-wheel>
uv pip check --python <tool-python>
```

These are command templates: substitute verified paths with proper shell
quoting. If dependency compatibility fails, resolve it against the project lock
before proceeding. Preserve package-age constraints. Do not mask packaging bugs
by modifying site-packages manually or using an editable install.

Restart only the identified AgentBridge service with its supervisor. For an
authorized launchd restart, the shape is
`launchctl kickstart -k gui/<uid>/<verified-label>`. For other supervisors, use
their existing service configuration. Do not restart an unrelated development
server or start a competing instance on the same port.

Poll `/health` in bounded intervals, sharing progress during a slow startup.
Confirm a changed start time/PID and inspect startup logs if readiness fails.
Navigate/reload the native browser after readiness. Verify installed source and
served branding against the built artifact, then rerun the repaired interactions.
If real provider execution is in scope, send a short synthetic probe, inspect its
saved completion, and confirm capacity returns to idle.

If installation or startup fails, report the failure and use the preserved local
artifact/configuration for rollback when safe within the authorized maintenance
scope. Do not claim success from the installer exit code alone. Local maintenance
does not imply a release, version bump, Git push, or PyPI publication.

## Diagnose uv lock configuration mismatches

Run ordinary `uv lock --check` first. A prior audit found that user-global
`exclude-newer-package` exemptions changed expected lock metadata despite
unchanged application dependencies.

When evidence identifies configuration inheritance as the cause:

1. Read `[tool.uv]` from the current `pyproject.toml` and the relevant global uv
   configuration without exposing unrelated private settings.
2. Create a temporary standalone uv config containing exactly the project's
   uv settings, converted from `[tool.uv]` to standalone root configuration.
   Preserve nested settings and supply-chain constraints. Use proper TOML
   parsing/serialization; do not assume this table is the file's last section.
3. Run `uv lock --check --config-file <temporary-project-config>`.
4. Report the normal failure and isolated project-config result separately.
   Do not rewrite the user's lockfile/global config to hide the mismatch.

`--no-config` is not equivalent: it also ignores the project's uv settings.
An isolated pass does not turn a failed ordinary check into a passed check.
