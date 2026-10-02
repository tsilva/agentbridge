---
name: agentbridge-dashboard-audit
description: "Audit the active local AgentBridge dashboard in the Codex in-app Browser, reproduce chat and Monitor bugs, implement requested fixes, and verify the running installation. Use for hands-on dashboard testing, repeated bug-finding and fixing, or local reinstall/restart/retest requests. Publishing releases belongs to build-release."
---

# AgentBridge Dashboard Audit

Test the instance the user actually runs. A passing source checkout does not prove
that the installed dashboard serves those changes.

## Establish the target and scope

1. Read repository instructions and the relevant README contract. Preserve local
   changes; follow the repository's current-branch synchronization rule once at
   the beginning of an editing task.
2. Identify the dashboard URL from the user's context and existing browser tabs.
   Verify `/health`; record version, start time, capacity, and active requests.
   Discover the listening process, launch command, installation, and supervisor
   when deployment verification is needed. Do not assume a port or launchd label.
3. Honor the requested mode: an audit reports findings; an audit-and-fix request
   includes repairs. Existing authorization for local reinstall/restart remains
   valid within the same task. Invocation alone does not authorize publishing,
   pushing, changing user configuration, or restarting unrelated services.
4. Use synthetic messages and generated attachments. Keep existing chats, logs,
   clipboard contents, and user files intact. Track only temporary resources
   created by this audit for cleanup.

## Initialize the native browser

Use the bundled Browser skill/runtime and the persistent Node REPL. Locate the
installed bundle rather than hardcoding a cache version. Follow its documented
`browser-client.mjs` bootstrap and select `agent.browsers.get("iab")`. Read the
returned browser documentation before using its APIs. If the bundle's skill
directory is empty, check its runtime and documentation before concluding that
browser testing is unavailable.

Reuse the user's dashboard tab for the real instance. Use owned temporary tabs
for isolated fixtures or fresh chat state. Drive the interface through documented
AX, CUA, or Playwright APIs; use fresh DOM/AX evidence after interactions. Browser
evaluation is limited to permitted DOM inspection, not calling application
functions, injecting state, or issuing API requests. Backend tools may prepare
fixtures and inspect logs, but do not replace browser verification.

Read runtime documentation for local development, uploads, and troubleshooting
when needed. Wait for health before navigating after a restart. Do not bypass
browser policy or switch to raw browser control when a tab operation fails.

## Audit, reproduce, and repair

Read [the audit checklist](references/audit-checklist.md). Cover Chat, Monitor,
navigation and persisted state, error handling, branding, and provider lifecycle
as applicable. Record tested branches and any untested areas.

For each candidate bug:

1. Record the trigger, expected behavior, observed result, and affected instance.
   Check browser state, the corresponding request log, and server evidence.
   Distinguish application defects from expected errors during deliberate
   disconnects, server startup, or browser attachment failures.
2. Reduce it to a deterministic reproduction. Use an isolated fixture server for
   malformed streams, timing races, and error responses. Reuse the actual
   dashboard router/templates/state with a temporary log directory, synthetic
   data, and an OS-assigned port. Keep the active instance running.
3. When fixes are requested, repair the cause and add a meaningful regression
   test for nontrivial failures. Relevant files include `agentbridge/dashboard.py`,
   `server.py`, `models.py`, `templates/dashboard/`, and the dashboard/server tests.
   Preserve the OpenAI response/error contract and saved-log schema. Update
   README when public behavior changes.
4. Rerun the reproduction through the browser and the relevant tests. Inspect
   exact prepared request bodies when checking retries or attachment races;
   visible text alone cannot establish that the right payload was sent.
5. Continue into other affected flows. For a repeated audit-and-fix request, run
   a complete scoped pass after the latest fix. Finish when that pass produces
   no new reproducible findings and required verification succeeds. Do not claim
   that testing proves no bugs exist. If a dependency prevents coverage, report
   the concrete limitation instead of treating that area as passed.

## Verify source and installed behavior

Run the repository's required checks after application changes:

```bash
uv run --frozen --extra test pytest -q
uv run --frozen --extra test ruff check agentbridge tests
uv lock --check
uv build
```

Check for skipped browser-client tests: `tests/test_dashboard_client.py` uses
Node when available. Report skips as a coverage gap. If lock checking fails,
diagnose project versus user-global uv configuration before changing the lock.
Global package exemptions have previously caused a metadata mismatch; see
[local installation and validation](references/local-install.md).

When the user requests local reinstall/restart, follow
[local installation and validation](references/local-install.md), then repeat
the relevant UI reproductions against the active instance. Verify the requested
default model and served logo/assets there. Use a small synthetic provider probe
to establish that the configured provider works when real execution is in scope;
inspect its saved completion and return to idle capacity.

## Finish

Stop owned fixture processes and close owned temporary tabs. Leave the user's
dashboard usable. Restore the clipboard after copy tests and retain requested
screenshots at absolute paths.

Report concrete fixes, browser coverage, check results, installation/restart
outcome when performed, and remaining findings or coverage gaps. Say "no new
reproducible issues in the final tested pass" only when that pass actually ran.
Do not commit, push, publish, or bump a version unless requested.
