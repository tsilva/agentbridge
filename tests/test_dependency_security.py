from __future__ import annotations

import tomllib
from importlib.metadata import version
from pathlib import Path

import jwt
import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from packaging.version import Version

ROOT = Path(__file__).resolve().parents[1]


def test_patched_dependency_versions_are_installed() -> None:
    floors = {
        "cryptography": "50.0.0",
        "idna": "3.15",
        "mcp": "1.28.1",
        "pydantic-settings": "2.14.2",
        "pygments": "2.20.0",
        "pyjwt": "2.13.0",
        "python-multipart": "0.0.31",
        "starlette": "1.3.1",
    }
    for package, floor in floors.items():
        assert Version(version(package)) >= Version(floor)


def test_pyjwt_accepts_expected_algorithm_and_rejects_unsigned_token() -> None:
    secret = "agentbridge-test-secret-is-32-bytes"
    signed = jwt.encode({"sub": "agentbridge"}, secret, algorithm="HS256")
    assert jwt.decode(signed, secret, algorithms=["HS256"])["sub"] == "agentbridge"

    unsigned = jwt.encode({"sub": "attacker"}, key="", algorithm="none")
    with pytest.raises(jwt.InvalidAlgorithmError):
        jwt.decode(unsigned, secret, algorithms=["HS256"])


def test_cryptography_verifies_valid_signature_and_rejects_tampering() -> None:
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    message = b"legitimate agentbridge payload"
    signature = private_key.sign(message)

    public_key.verify(signature, message)
    with pytest.raises(InvalidSignature):
        public_key.verify(signature, b"tampered agentbridge payload")


def test_dependency_manifests_use_registry_sources_only() -> None:
    with (ROOT / "pyproject.toml").open("rb") as file:
        manifest = tomllib.load(file)
    with (ROOT / "uv.lock").open("rb") as file:
        lock = tomllib.load(file)

    declared = list(manifest["project"]["dependencies"])
    for dependencies in manifest["project"].get("optional-dependencies", {}).values():
        declared.extend(dependencies)
    assert not any(
        dependency.lower().startswith(("file:", "git:", "git+", "http:", "https:"))
        for dependency in declared
    )

    for package in lock["package"]:
        source = package.get("source", {})
        if package["name"] == "agentbridge-cli" and set(source) & {
            "editable",
            "virtual",
            "directory",
        }:
            continue
        assert source == {"registry": "https://pypi.org/simple"}
