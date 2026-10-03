---
name: build-release
description: Build, publish, and verify AgentBridge releases. Use when the user invokes /build-release or asks to cut, launch, tag, publish, monitor, or verify the agentbridge-cli PyPI package or macOS app.
---

# Build Release

Read and apply the shared `$release-workflow` skill at
`/Users/tsilva/.codex/skills/release-workflow/SKILL.md` before execution.
It owns common preflight, publication safeguards, `$push` integration,
workflow monitoring, verification, and reporting. The rules below are this
project's adapter; they retain its invocation default and required gates.
If the shared skill is unavailable, stop and report the missing dependency.

A bare `$build-release` or `/build-release` invocation requests the full
publication flow below. Normal publication and validation build exclusively in
GitHub Actions. The operator needs Python 3.11+, Git, `gh`, and `uv` only for
version/lockfile preparation; no local Swift, Xcode, or application build is required.

Use the repository-owned GitHub Actions workflow and PyPI Trusted Publishing.
Do not create a local tag or upload with local credentials: pushing a new
`pyproject.toml` version to `main` triggers `.github/workflows/release.yml`,
which tests, scans, builds, creates `v<version>`, creates the GitHub Release,
publishes `agentbridge-cli`, and attaches an ad-hoc-signed arm64 DMG.

Use the next unused patch version unless the user requests another valid,
unused semantic version. Treat an untagged version absent from PyPI as pending.

## Flow

1. Fetch release state and require a clean, synchronized `main` worktree:

```bash
git fetch origin main --tags
git status --short --branch
git log --oneline origin/main..HEAD
git log --oneline HEAD..origin/main
```

Stop on unrelated changes, unpublished commits, divergence, or another branch.
Do not clean, pull, commit unrelated files, or switch branches.

The macOS artifacts use an ad-hoc signature and are not notarized. They do not
require Apple Developer credentials or repository secrets.

2. Select the release version from the repository root:

```bash
python3 .codex/skills/build-release/scripts/release_build.py next-version
```

Update only `[project].version` in `pyproject.toml` with `apply_patch`, then
refresh the lockfile mechanically:

```bash
uv lock
```

3. Check metadata and patch formatting without compiling locally:

```bash
python3 .codex/skills/build-release/scripts/release_build.py ci-metadata --require-unused
git diff --check
```

Actions checks the frozen lock, Python 3.12/3.13 tests, dependency audit, Ruff,
secret scan, Swift tests, wheel/sdist contents and metadata, an isolated wheel
installation, and the arm64 app/DMG signature, embedded runtime, and checksum.
Both package and macOS gates must pass before PyPI or GitHub publication.
Stop at the exact failed gate.

4. Review and publish the release commit using the shared `$push` procedure:

```bash
git diff --check
git diff -- pyproject.toml uv.lock
git status --short
git add pyproject.toml uv.lock <other-intended-release-files>
git commit -m "Release <version>"
release_sha="$(git rev-parse HEAD)"
git push origin HEAD:main
```

Do not create the tag locally; the release workflow owns it.

5. Follow shared monitoring for the `release.yml` `push` run at the pushed
release commit SHA. A manual dispatch publishes only when its `publish` input
is explicitly true.

6. Verify exact-version PyPI files and GitHub assets:

```bash
python3 .codex/skills/build-release/scripts/release_build.py wait-pypi --version <version>
```

Require `AgentBridge-<version>-macos-arm64.dmg` and its `.sha256` file on the
`v<version>` GitHub Release, alongside the Python distributions.
Confirm the tag resolves to the pushed release SHA and download the assets to
verify their checksums. Do not infer publication from a successful validation run.

## Validation without publication

Validate committed `origin/main` in Actions without a version bump or local build:

```bash
python3 .codex/skills/build-release/scripts/release_build.py validate
```

This may run with a dirty local worktree: only committed remote source is tested.
Monitor the `workflow_dispatch` run on `main` at the helper's printed full SHA;
stop if its `headSha` differs. Require both Python and macOS build jobs, download
`python-package-<sha>` and `macos-app-arm64-<sha>`, and check the DMG checksum.
The run must skip `publish`, `release`, and `attach-macos`. Report that no new
release was published.

For an explicitly requested local build, use the retained macOS-only helper:

```bash
python3 .codex/skills/build-release/scripts/release_build.py preflight --version <unused-version>
```

This local preflight builds and tests locally and requires an unused version;
never run it as part of normal `$build-release` publication or Actions validation.

## Missing macOS assets

If an existing release is missing only its macOS assets, attach them without
republishing Python distributions:

```bash
gh workflow run release.yml --ref main -f attach_macos=true
```
