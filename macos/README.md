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

Install [uv](https://docs.astral.sh/uv/) and the Xcode Command Line Tools, then
run this command from the repository root:

```bash
scripts/build_macos_app.sh
```

The script builds the Swift executable, embeds a uv-managed Python 3.12 runtime
and the locked AgentBridge dependencies, applies an ad-hoc signature for local
use, and creates a DMG for the current Mac architecture under
`build/macos/<architecture>/`. Building and running this local app does not
require an Apple Developer account.

Open the generated DMG and drag `AgentBridge.app` to Applications.

Mutable data stays outside the application bundle:

```text
~/.config/agentbridge/.env
~/.config/agentbridge/logs/
```
