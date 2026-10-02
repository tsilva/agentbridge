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
publication flow below. An explicitly local build or verification request uses
only the corresponding non-publishing checks.

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

3. Run the deterministic release preflight with the exact version:

```bash
python3 .codex/skills/build-release/scripts/release_build.py preflight --version <version>
```

The preflight requires macOS. It checks consistent project and lock metadata, an
unused PyPI version and tag, clean patch formatting, a frozen lock, Python 3.12
and 3.13 tests, Ruff, Swift tests, a self-contained app/DMG build for the current
Mac architecture, app signature and embedded-runtime smoke tests, wheel and
sdist audits, and a wheel installation smoke test. CI builds the arm64 macOS
artifact with an ad-hoc signature. Stop at the exact failed gate.

4. Review and publish the release commit:

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

If an existing release is missing only its macOS assets, attach them without
republishing Python distributions:

```bash
gh workflow run release.yml --ref main -f attach_macos=true
```
