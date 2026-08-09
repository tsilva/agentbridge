"""AgentBridge - OpenAI-compatible API for Claude Code SDK and Codex CLI."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("agentbridge-py")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"
