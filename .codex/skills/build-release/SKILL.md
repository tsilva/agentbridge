---
name: build-release
description: Build, publish, and verify AgentBridge releases. Use when the user invokes /build-release or asks to cut, launch, tag, publish, monitor, or verify an agentbridge-cli PyPI or GitHub release.
---

# Build Release

Use the repository-owned GitHub Actions workflow and PyPI Trusted Publishing.
Do not create a local tag or upload with local credentials: pushing a new
`pyproject.toml` version to `main` triggers `.github/workflows/release.yml`,
which tests, scans, builds, creates `v<version>`, creates the GitHub Release,
and publishes `agentbridge-cli`.

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

The preflight requires consistent project and lock metadata, an unused PyPI
version and tag, clean patch formatting, a frozen lock, passing tests on Python
3.12 and 3.13, Ruff, a successful wheel and sdist build, artifact audits, and a
wheel installation smoke test. Stop at the exact failed gate.

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

Never stage unrelated user changes. Do not create the tag locally; the release
workflow owns it.

5. Find and monitor the release workflow for the pushed commit:

```bash
gh run list --workflow release.yml --commit "$release_sha" --limit 5 \
  --json databaseId,status,conclusion,event,headSha,url
gh run watch <run-id> --exit-status
```

If the commit-filtered result has not appeared, poll briefly. Select the
`push` run for the exact SHA. A manual dispatch publishes only when its
`publish` input is explicitly true.

6. After the workflow succeeds, verify exact-version files on PyPI and inspect
the GitHub Release:

```bash
python3 .codex/skills/build-release/scripts/release_build.py wait-pypi --version <version>
gh release view v<version> --json url,tagName,assets
```

Do not report success until PyPI returns files for the exact version. If the
workflow fails, inspect `gh run view <run-id> --log-failed` and report the
failed gate before considering recovery.

## Final Response

Lead with the exact PyPI version URL. Report the tag, release workflow URL and
conclusion, GitHub Release URL, pushed commit, and every distribution filename.
On failure, report the exact command or job and the next safe recovery action.
