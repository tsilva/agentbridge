#!/usr/bin/env python3
"""Select, build, audit, and verify agentbridge-py releases."""

from __future__ import annotations

import argparse
import email.parser
import hashlib
import json
import re
import subprocess
import sys
import tarfile
import tempfile
import time
import tomllib
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
PACKAGE_NAME = "agentbridge-py"
IMPORT_NAME = "agentbridge"
VERSION_PATTERN = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
TEST_PYTHONS = ("3.12", "3.13")


def run(args: list[str], *, capture: bool = False) -> str:
    print("+", " ".join(args), flush=True)
    result = subprocess.run(
        args,
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
    )
    return result.stdout.strip() if capture else ""


def read_toml(path: Path) -> dict[str, object]:
    with path.open("rb") as stream:
        return tomllib.load(stream)


def parse_version(version: str) -> tuple[int, int, int]:
    match = VERSION_PATTERN.fullmatch(version)
    if match is None:
        raise SystemExit(f"release version must be MAJOR.MINOR.PATCH: {version!r}")
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def project_metadata() -> dict[str, object]:
    project = read_toml(REPO_ROOT / "pyproject.toml").get("project")
    if not isinstance(project, dict):
        raise SystemExit("pyproject.toml is missing [project]")
    return project


def project_version() -> str:
    version = project_metadata().get("version")
    if not isinstance(version, str):
        raise SystemExit("project.version must be a string")
    parse_version(version)
    return version


def lock_version() -> str:
    packages = read_toml(REPO_ROOT / "uv.lock").get("package", [])
    if not isinstance(packages, list):
        raise SystemExit("uv.lock has an invalid package list")
    for package in packages:
        if isinstance(package, dict) and package.get("name") == PACKAGE_NAME:
            version = package.get("version")
            if isinstance(version, str):
                return version
    raise SystemExit(f"uv.lock is missing {PACKAGE_NAME!r}")


def fetch_pypi() -> dict[str, object]:
    url = f"https://pypi.org/pypi/{PACKAGE_NAME}/json"
    try:
        with urllib.request.urlopen(url, timeout=20) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return {}
        raise
    if not isinstance(data, dict):
        raise SystemExit("unexpected PyPI JSON response")
    return data


def pypi_files(version: str) -> list[dict[str, object]]:
    releases = fetch_pypi().get("releases", {})
    if not isinstance(releases, dict):
        raise SystemExit("unexpected PyPI releases payload")
    files = releases.get(version, [])
    if not isinstance(files, list):
        raise SystemExit(f"unexpected PyPI file payload for {version}")
    return [item for item in files if isinstance(item, dict)]


def next_version(_: argparse.Namespace) -> None:
    candidate = project_version()
    releases = fetch_pypi().get("releases", {})
    if not isinstance(releases, dict):
        raise SystemExit("unexpected PyPI releases payload")
    while releases.get(candidate):
        major, minor, patch = parse_version(candidate)
        candidate = f"{major}.{minor}.{patch + 1}"
    print(candidate)


def tag_exists(version: str) -> bool:
    tag = f"v{version}"
    local = subprocess.run(
        ["git", "rev-parse", "-q", "--verify", f"refs/tags/{tag}"],
        cwd=REPO_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    remote = subprocess.run(
        ["git", "ls-remote", "--exit-code", "--tags", "origin", f"refs/tags/{tag}"],
        cwd=REPO_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return local.returncode == 0 or remote.returncode == 0


def check_version(version: str) -> None:
    parse_version(version)
    project = project_metadata()
    actual = {
        "project.name": project.get("name"),
        "project.version": project.get("version"),
        "project.requires-python": project.get("requires-python"),
        "uv.lock version": lock_version(),
    }
    expected = {
        "project.name": PACKAGE_NAME,
        "project.version": version,
        "project.requires-python": ">=3.12",
        "uv.lock version": version,
    }
    mismatches = {
        key: value for key, value in actual.items() if value != expected[key]
    }
    if mismatches:
        details = ", ".join(
            f"{key}={value!r}, expected {expected[key]!r}"
            for key, value in mismatches.items()
        )
        raise SystemExit(f"release metadata mismatch: {details}")
    if pypi_files(version):
        raise SystemExit(f"{PACKAGE_NAME}=={version} already exists on PyPI")
    if tag_exists(version):
        raise SystemExit(f"v{version} already exists locally or on origin")
    print(json.dumps(actual, indent=2))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def is_private_environment_file(name: str) -> bool:
    basename = Path(name).name
    return basename == ".env" or (
        basename.startswith(".env.") and not basename.endswith(".example")
    )


def audit_wheel(wheel: Path, version: str) -> dict[str, object]:
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        metadata_name = next(
            (name for name in names if name.endswith(".dist-info/METADATA")),
            None,
        )
        entry_points_name = next(
            (name for name in names if name.endswith(".dist-info/entry_points.txt")),
            None,
        )
        metadata = (
            email.parser.Parser().parsestr(archive.read(metadata_name).decode())
            if metadata_name is not None
            else None
        )
        entry_points = (
            archive.read(entry_points_name).decode()
            if entry_points_name is not None
            else ""
        )
    required = {
        f"{IMPORT_NAME}/__init__.py",
        f"{IMPORT_NAME}/server.py",
        f"{IMPORT_NAME}/dashboard.py",
        f"{IMPORT_NAME}/models.py",
        f"{IMPORT_NAME}/pool.py",
        f"{IMPORT_NAME}/config.py",
        f"{IMPORT_NAME}/_build_info.py",
        f"{IMPORT_NAME}/templates/dashboard/base.html",
        f"{IMPORT_NAME}/templates/dashboard/chat.html",
        f"{IMPORT_NAME}/templates/dashboard/detail.html",
        f"{IMPORT_NAME}/templates/dashboard/page.html",
        f"{IMPORT_NAME}/templates/dashboard/pool.html",
        f"{IMPORT_NAME}/templates/dashboard/requests.html",
    }
    checks = {
        "filename_version": version in wheel.name,
        "universal_wheel": wheel.name.endswith("-py3-none-any.whl"),
        "metadata_name": metadata is not None and metadata.get("Name") == PACKAGE_NAME,
        "metadata_version": metadata is not None and metadata.get("Version") == version,
        "requires_python": metadata is not None and metadata.get("Requires-Python") == ">=3.12",
        "console_script": "agentbridge = agentbridge.server:main" in entry_points,
        "required_package_files": required.issubset(names),
        "has_license": any(name.endswith(".dist-info/licenses/LICENSE") for name in names),
        "no_cache_files": not any(
            "__pycache__" in Path(name).parts or name.endswith(".pyc")
            for name in names
        ),
        "no_private_environment_files": not any(
            is_private_environment_file(name) for name in names
        ),
    }
    failed = [name for name, passed in checks.items() if not passed]
    result = {"file": wheel.name, "sha256": sha256(wheel), "checks": checks}
    if failed:
        print(json.dumps(result, indent=2), file=sys.stderr)
        raise SystemExit(f"wheel audit failed: {failed}")
    return result


def audit_sdist(sdist: Path, version: str) -> dict[str, object]:
    with tarfile.open(sdist, "r:gz") as archive:
        members = archive.getmembers()
        names = [member.name for member in members]
        pyproject_member = next(
            (member for member in members if member.name.endswith("/pyproject.toml")),
            None,
        )
        if pyproject_member is None:
            raise SystemExit("sdist is missing pyproject.toml")
        stream = archive.extractfile(pyproject_member)
        if stream is None:
            raise SystemExit("could not read pyproject.toml from sdist")
        built_project = tomllib.loads(stream.read().decode()).get("project", {})
    forbidden_parts = {".git", ".venv", "__pycache__", "dist", "logs"}
    checks = {
        "filename_version": version in sdist.name,
        "metadata_name": (
            isinstance(built_project, dict)
            and built_project.get("name") == PACKAGE_NAME
        ),
        "metadata_version": (
            isinstance(built_project, dict)
            and built_project.get("version") == version
        ),
        "has_license": any(name.endswith("/LICENSE") for name in names),
        "has_readme": any(name.endswith("/README.md") for name in names),
        "has_build_hook": any(name.endswith("/hatch_build.py") for name in names),
        "has_package": any(name.endswith(f"/{IMPORT_NAME}/server.py") for name in names),
        "no_build_outputs": not any(
            forbidden_parts.intersection(Path(name).parts) for name in names
        ),
        "no_private_environment_files": not any(
            is_private_environment_file(name) for name in names
        ),
    }
    failed = [name for name, passed in checks.items() if not passed]
    result = {"file": sdist.name, "sha256": sha256(sdist), "checks": checks}
    if failed:
        print(json.dumps(result, indent=2), file=sys.stderr)
        raise SystemExit(f"sdist audit failed: {failed}")
    return result


def smoke_wheel(wheel: Path, version: str) -> None:
    python = run(["uv", "python", "find", "3.12"], capture=True)
    with tempfile.TemporaryDirectory(prefix="agentbridge-smoke-") as directory:
        environment = Path(directory) / "venv"
        run(["uv", "venv", "--python", python, str(environment)])
        installed_python = environment / "bin" / "python"
        run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(installed_python),
                "--no-deps",
                str(wheel),
            ]
        )
        code = (
            "from importlib.metadata import version; "
            "import agentbridge; "
            f"assert version('{PACKAGE_NAME}') == '{version}'; "
            f"assert agentbridge.__version__ == '{version}'; "
            "print(agentbridge.__version__)"
        )
        run([str(installed_python), "-c", code])


def preflight(args: argparse.Namespace) -> None:
    version = args.version
    check_version(version)
    run(["git", "diff", "--check"])
    run(["uv", "lock", "--check"])
    for python in TEST_PYTHONS:
        run(
            [
                "uv",
                "run",
                "--frozen",
                "--extra",
                "test",
                "--python",
                python,
                "pytest",
                "-q",
            ]
        )
    run(
        [
            "uv",
            "run",
            "--frozen",
            "--extra",
            "test",
            "--python",
            TEST_PYTHONS[0],
            "ruff",
            "check",
            "agentbridge",
            "tests",
            ".codex/skills/build-release/scripts/release_build.py",
        ]
    )
    with tempfile.TemporaryDirectory(prefix="agentbridge-release-") as directory:
        output = Path(directory) / "dist"
        run(["uv", "build", "--out-dir", str(output)])
        wheels = sorted(output.glob("*.whl"))
        sdists = sorted(output.glob("*.tar.gz"))
        artifacts = [path for path in output.iterdir() if path.name != ".gitignore"]
        if len(wheels) != 1 or len(sdists) != 1 or len(artifacts) != 2:
            raise SystemExit(
                f"expected one wheel and one sdist, found {sorted(path.name for path in artifacts)}"
            )
        results = [audit_wheel(wheels[0], version), audit_sdist(sdists[0], version)]
        smoke_wheel(wheels[0], version)
        print(
            json.dumps(
                {"package": PACKAGE_NAME, "version": version, "artifacts": results},
                indent=2,
            )
        )


def wait_pypi(args: argparse.Namespace) -> None:
    parse_version(args.version)
    for attempt in range(1, args.attempts + 1):
        files = pypi_files(args.version)
        if files:
            print(f"https://pypi.org/project/{PACKAGE_NAME}/{args.version}/")
            for item in files:
                filename = item.get("filename")
                if isinstance(filename, str):
                    print(filename)
            return
        print(f"waiting for {PACKAGE_NAME} {args.version} ({attempt}/{args.attempts})", flush=True)
        time.sleep(args.interval)
    raise SystemExit(f"{PACKAGE_NAME} {args.version} did not appear on PyPI")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    next_parser = commands.add_parser("next-version")
    next_parser.set_defaults(func=next_version)

    preflight_parser = commands.add_parser("preflight")
    preflight_parser.add_argument("--version", required=True)
    preflight_parser.set_defaults(func=preflight)

    wait_parser = commands.add_parser("wait-pypi")
    wait_parser.add_argument("--version", required=True)
    wait_parser.add_argument("--attempts", type=int, default=60)
    wait_parser.add_argument("--interval", type=float, default=10)
    wait_parser.set_defaults(func=wait_pypi)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
