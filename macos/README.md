# AgentBridge for macOS

The macOS companion is a native SwiftUI menu-bar app. It owns an embedded
AgentBridge server process, displays live `/health` state, and opens the existing
dashboard. Claude Code and Codex executables remain external and use the current
user's authentication state.

## Develop

```bash
cd macos
swift test
swift run AgentBridgeMenuBar
```

`swift run` uses an `agentbridge` executable found on `PATH`. Override it when
needed:

```bash
AGENTBRIDGE_SERVER_EXECUTABLE=/absolute/path/to/agentbridge \
  swift run AgentBridgeMenuBar
```

## Build the self-contained application

```bash
scripts/build_macos_app.sh
```

The script builds the Swift executable, embeds a uv-managed Python 3.12 runtime
and the locked AgentBridge dependencies, applies an ad-hoc signature for local
testing, and creates a DMG under `build/macos/<architecture>/`.

Set `CODE_SIGN_IDENTITY` to a Developer ID Application identity for a release
build. Notarization is performed by the release workflow after the DMG is built.

Mutable data stays outside the application bundle:

```text
~/.config/agentbridge/.env
~/.config/agentbridge/logs/
```
