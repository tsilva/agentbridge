#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 /path/to/AgentBridge.app" >&2
    exit 2
fi

app_path="$1"
server_root="${app_path}/Contents/Resources/server"
python_path="${server_root}/python/bin/python3"

test -x "${app_path}/Contents/MacOS/AgentBridgeMenuBar"
test -x "${python_path}"
test -d "${server_root}/site-packages/agentbridge"
test ! -e "${server_root}/site-packages/claude_agent_sdk/_bundled/claude"
plutil -lint "${app_path}/Contents/Info.plist"
codesign --verify --deep --strict --verbose=2 "${app_path}"

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="${server_root}/site-packages" \
    "${python_path}" -c \
    'from agentbridge.server import get_version; print(get_version())'

echo "Verified self-contained AgentBridge app: ${app_path}"
