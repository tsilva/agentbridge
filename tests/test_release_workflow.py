"""Release metadata, remote validation dispatch, and distribution gate regressions."""

import argparse
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

HELPER = (
    Path(__file__).resolve().parents[1]
    / '.codex/skills/build-release/scripts/release_build.py'
)
SPEC = importlib.util.spec_from_file_location('release_build', HELPER)
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


class ReleaseWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root_patch = patch.object(release, 'REPO_ROOT', self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.write_metadata('1.2.3', '1.2.3')

    def write_metadata(self, project, lock):
        (self.root / 'pyproject.toml').write_text(
            f'[project]\nname="agentbridge-cli"\nversion="{project}"\nrequires-python=">=3.12"\n'
        )
        (self.root / 'uv.lock').write_text(
            f'[[package]]\nname="agentbridge-cli"\nversion="{lock}"\n'
        )

    def test_validation_metadata_allows_published_version_without_network(self):
        with patch.object(release, 'fetch_pypi', side_effect=AssertionError('network')), \
             patch.object(release, 'tag_exists', side_effect=AssertionError('tag query')):
            release.ci_metadata(argparse.Namespace(require_unused=False))

    def test_metadata_rejects_out_of_date_lock(self):
        self.write_metadata('1.2.3', '1.2.2')
        with self.assertRaisesRegex(SystemExit, 'metadata mismatch'):
            release.ci_metadata(argparse.Namespace(require_unused=False))

    def test_publication_rejects_existing_pypi_version(self):
        with patch.object(release, 'pypi_files', return_value=[{'filename': 'existing.whl'}]):
            with self.assertRaisesRegex(SystemExit, 'already exists on PyPI'):
                release.check_version('1.2.3')

    def test_publication_rejects_existing_tag(self):
        with patch.object(release, 'pypi_files', return_value=[]), \
             patch.object(release, 'tag_exists', return_value=True):
            with self.assertRaisesRegex(SystemExit, 'already exists locally or on origin'):
                release.check_version('1.2.3')

    def test_tag_network_failure_does_not_claim_version_unused(self):
        with patch.object(
            release.subprocess, 'run', side_effect=[Mock(returncode=1), Mock(returncode=128)]
        ):
            with self.assertRaisesRegex(SystemExit, 'could not check release tags'):
                release.tag_exists('1.2.3')

    def test_next_version_skips_tagged_but_unpublished_version(self):
        with patch.object(release, 'fetch_pypi', return_value={'releases': {}}), \
             patch.object(release, 'tag_exists', side_effect=[True, False]), \
             patch('builtins.print') as output:
            release.next_version(argparse.Namespace())
        output.assert_called_once_with('1.2.4')

    def test_remote_validation_never_uses_local_metadata_or_build_tools(self):
        (self.root / 'pyproject.toml').write_text('dirty invalid local metadata')
        calls = []

        def run(command, **kwargs):
            calls.append(command)
            if command == ['git', 'rev-parse', 'origin/main']:
                return 'a' * 40
            if command[0] not in {'git', 'gh'}:
                self.fail(f'local build command: {command}')
            return ''

        with patch.object(release, 'run', side_effect=run):
            release.validate(argparse.Namespace())
        self.assertEqual(calls[-1], [
            'gh', 'workflow', 'run', 'release.yml', '--ref', 'main',
            '-f', 'publish=false', '-f', 'attach_macos=false',
        ])
        self.assertEqual(calls[1:3], [
            ['git', 'fetch', 'origin', 'main'], ['git', 'rev-parse', 'origin/main'],
        ])

    def test_failed_fetch_stops_before_dispatch(self):
        with patch.object(release, 'run', side_effect=['', RuntimeError('fetch failed')]) as run:
            with self.assertRaisesRegex(RuntimeError, 'fetch failed'):
                release.validate(argparse.Namespace())
        self.assertEqual(run.call_count, 2)

    def test_distribution_gate_rejects_extra_file_before_install(self):
        dist = self.root / 'dist'
        dist.mkdir()
        for name in ('package.whl', 'package.tar.gz', 'unexpected.txt'):
            (dist / name).touch()
        with patch.object(release, 'smoke_wheel') as smoke:
            with self.assertRaisesRegex(SystemExit, 'exactly one wheel and one sdist'):
                release.audit_dist(argparse.Namespace(directory=str(dist)))
        smoke.assert_not_called()

    def test_distribution_audit_failure_stops_installation(self):
        dist = self.root / 'dist'
        dist.mkdir()
        (dist / 'package.whl').touch()
        (dist / 'package.tar.gz').touch()
        with patch.object(release, 'audit_wheel', side_effect=SystemExit('invalid wheel')), \
             patch.object(release, 'smoke_wheel') as smoke:
            with self.assertRaisesRegex(SystemExit, 'invalid wheel'):
                release.audit_dist(argparse.Namespace(directory=str(dist)))
        smoke.assert_not_called()

    def test_distribution_gate_audits_and_installs_exact_wheel(self):
        dist = self.root / 'dist'
        dist.mkdir()
        wheel = dist / 'package.whl'
        sdist = dist / 'package.tar.gz'
        wheel.touch()
        sdist.touch()
        with patch.object(release, 'audit_wheel', return_value={}) as audit_wheel, \
             patch.object(release, 'audit_sdist', return_value={}) as audit_sdist, \
             patch.object(release, 'smoke_wheel') as smoke:
            release.audit_dist(argparse.Namespace(directory=str(dist)))
        audit_wheel.assert_called_once_with(wheel, '1.2.3')
        audit_sdist.assert_called_once_with(sdist, '1.2.3')
        smoke.assert_called_once_with(wheel, '1.2.3')


if __name__ == '__main__':
    unittest.main()
