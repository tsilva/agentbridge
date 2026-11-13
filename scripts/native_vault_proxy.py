"""Trusted native-proxy bootstrap. Never sends upstream keys to app processes."""

import hashlib
import hmac
import json
import os
import re
import ssl
import stat
import subprocess
import sys
from pathlib import Path
from uuid import UUID

PREFIX = Path.home() / ".config/infisical"
PROFILE = PREFIX / "native-proxy/agentbridge.json"
CLI = PREFIX / "cli/0.45.6/infisical"
INSTANCE = "https://app.infisical.com"
SOURCE_SECRET = "AGENT_VAULT_PROXY_TOKEN"
CA_SECRET = "AGENT_VAULT_CA_PRIVATE_KEY"


class BootstrapError(Exception):
    """A fixed diagnostic which contains no credentials or provider response."""


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise BootstrapError("Duplicate bootstrap metadata")
        result[key] = value
    return result


def protected(path, directory=False):
    info = path.lstat()
    expected = stat.S_ISDIR if directory else stat.S_ISREG
    if path.resolve() != path or not expected(info.st_mode):
        raise BootstrapError("Bootstrap metadata must be canonical regular paths")
    if info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise BootstrapError("Bootstrap metadata must be owner-only")


def load(path):
    protected(path.parent, directory=True)
    protected(path)
    p = json.loads(path.read_text(), object_pairs_hook=json_object)
    expected = {
        "version",
        "instance",
        "source_project_id",
        "environment",
        "secret_path",
        "secret_name",
        "proxy_id",
        "port",
        "infisical",
        "cli_sha256",
        "self_sha256",
        "token_sha256",
        "ca_fingerprint",
        "ca_private_sha256",
        "ca_file",
        "ca_file_sha256",
    }
    if not isinstance(p, dict) or set(p) != expected:
        raise BootstrapError("Unreviewed bootstrap metadata")
    if (
        type(p["version"]) is not int
        or p["version"] != 1
        or p["instance"] != INSTANCE
        or p["environment"] != "dev"
        or p["secret_path"] != "/proxy"
        or p["secret_name"] != SOURCE_SECRET
        or type(p["port"]) is not int
        or p["port"] != 8283
        or p["infisical"] != str(CLI)
    ):
        raise BootstrapError("Unreviewed proxy or source scope")
    for key in ["source_project_id", "proxy_id"]:
        if str(UUID(p[key])) != p[key]:
            raise BootstrapError("Invalid source identity")
    for key in [
        "cli_sha256",
        "self_sha256",
        "token_sha256",
        "ca_private_sha256",
        "ca_file_sha256",
    ]:
        if not isinstance(p[key], str) or not re.fullmatch("[a-f0-9]{64}", p[key]):
            raise BootstrapError("Invalid bootstrap pin")
    if not re.fullmatch(r"SHA256:(?:[0-9A-F]{2}:){31}[0-9A-F]{2}", p["ca_fingerprint"]):
        raise BootstrapError("Invalid proxy CA pin")
    if digest(CLI) != p["cli_sha256"] or digest(Path(__file__)) != p["self_sha256"]:
        raise BootstrapError("Bootstrap runtime changed; trusted review required")
    ca = Path(p["ca_file"])
    if ca.resolve() != ca or digest(ca) != p["ca_file_sha256"]:
        raise BootstrapError("Proxy public CA file changed")
    pem = ca.read_text()
    if "PRIVATE KEY" in pem:
        raise BootstrapError("Expected only the public CA certificate")
    fingerprint = hashlib.sha256(ssl.PEM_cert_to_DER_cert(pem)).hexdigest().upper()
    if fingerprint != p["ca_fingerprint"].removeprefix("SHA256:").replace(":", ""):
        raise BootstrapError("Proxy public CA does not match its reviewed fingerprint")
    return p


def read_source(p, name):
    clean = {"HOME": str(Path.home()), "PATH": "/usr/bin:/bin"}
    command = [
        p["infisical"],
        "secrets",
        "get",
        name,
        "--plain",
        "--projectId=" + p["source_project_id"],
        "--env=dev",
        "--path=/proxy",
        "--domain=" + INSTANCE,
        "--expand=false",
        "--include-imports=false",
        "--secret-overriding=false",
        "--silent",
        "--telemetry=false",
    ]
    result = subprocess.run(
        command,
        env=clean,
        cwd="/",
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=35,
    )
    if result.returncode:
        raise BootstrapError("Proxy bootstrap requires Infisical login or source renewal")
    return result.stdout.strip()


def start(p):
    clean = {"HOME": str(Path.home()), "PATH": "/usr/bin:/bin"}
    token = read_source(p, SOURCE_SECRET)
    if not re.fullmatch(r"[A-Za-z0-9_.=-]{16,8192}", token) or not hmac.compare_digest(
        hashlib.sha256(token.encode()).hexdigest(), p["token_sha256"]
    ):
        raise BootstrapError("Proxy bootstrap value differs from the reviewed source")
    key = read_source(p, CA_SECRET) + "\n"
    if (
        len(key) > 8192
        or "PRIVATE KEY-----" not in key
        or not hmac.compare_digest(hashlib.sha256(key.encode()).hexdigest(), p["ca_private_sha256"])
    ):
        raise BootstrapError("Proxy private CA differs from the reviewed source")
    # Only the native proxy receives this administrative token. It loads service
    # credentials itself; ordinary apps receive separate scoped session capabilities.
    environment = {
        **clean,
        "INFISICAL_AGENT_VAULT_PROXY_TOKEN": token,
        "INFISICAL_AGENT_VAULT_CA_KEY": key,
    }
    argv = [
        p["infisical"],
        "agent-vault",
        "proxy",
        "--domain=" + INSTANCE,
        "--port=8283",
        "--data-dir=/dev/null",
        "--log-level=error",
        "--ca-cert=" + p["ca_file"],
        "--silent",
        "--telemetry=false",
    ]
    os.execve(p["infisical"], argv, environment)


def main(args):
    if args:
        raise BootstrapError("This supervisor accepts only its protected registered profile")
    start(load(PROFILE))


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except Exception:  # noqa: BLE001 -- bootstrap credentials must never reach logs
        print("Native Vault proxy bootstrap failed; details withheld", file=sys.stderr)
        sys.exit(1)
