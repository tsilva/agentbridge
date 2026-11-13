"""Offline administrative bootstrap tests with synthetic values only."""

import hashlib
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "bootstrap", Path(__file__).with_name("native_vault_proxy.py")
)
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)

FAKE_TOKEN = "fake-native-proxy-bootstrap-token-for-tests-only"
FAKE_KEY = "-----BEGIN PRIVATE KEY-----\nsynthetic-test-fixture-only\n-----END PRIVATE KEY-----\n"


class BootstrapTests(unittest.TestCase):
    def profile(self):
        return {
            "infisical": str(bootstrap.CLI),
            "source_project_id": "00000000-0000-4000-8000-000000000001",
            "token_sha256": hashlib.sha256(FAKE_TOKEN.encode()).hexdigest(),
            "ca_private_sha256": hashlib.sha256(FAKE_KEY.encode()).hexdigest(),
            "ca_file": "/synthetic/public-ca.pem",
        }

    def test_only_native_proxy_receives_token_and_no_secret_in_arguments(self):
        completed = subprocess.CompletedProcess([], 0, FAKE_TOKEN + "\n", "")
        private = subprocess.CompletedProcess([], 0, FAKE_KEY, "")
        with patch.object(bootstrap.subprocess, "run", side_effect=[completed, private]) as read:
            with patch.object(bootstrap.os, "execve") as launch:
                bootstrap.start(self.profile())
        source = read.call_args
        self.assertIn("--expand=false", source.args[0])
        self.assertIn("--include-imports=false", source.args[0])
        self.assertEqual(
            [call.args[0][3] for call in read.call_args_list],
            [bootstrap.SOURCE_SECRET, bootstrap.CA_SECRET],
        )
        self.assertEqual(set(source.kwargs["env"]), {"HOME", "PATH"})
        executable, argv, env = launch.call_args.args
        self.assertEqual(executable, str(bootstrap.CLI))
        self.assertNotIn(FAKE_TOKEN, " ".join(argv))
        self.assertNotIn(FAKE_KEY, " ".join(argv))
        self.assertIn("--data-dir=/dev/null", argv)
        self.assertEqual(env["INFISICAL_AGENT_VAULT_PROXY_TOKEN"], FAKE_TOKEN)
        self.assertEqual(env["INFISICAL_AGENT_VAULT_CA_KEY"], FAKE_KEY)
        self.assertEqual(
            set(env),
            {"HOME", "PATH", "INFISICAL_AGENT_VAULT_PROXY_TOKEN", "INFISICAL_AGENT_VAULT_CA_KEY"},
        )

    def test_wrong_source_and_provider_errors_never_start_proxy_or_echo_value(self):
        for completed in [
            subprocess.CompletedProcess([], 1, FAKE_TOKEN, FAKE_TOKEN),
            subprocess.CompletedProcess([], 0, "different-fake-token-value", ""),
            subprocess.CompletedProcess([], 0, FAKE_TOKEN + "\nreflected-header", ""),
        ]:
            with patch.object(bootstrap.subprocess, "run", return_value=completed):
                with patch.object(bootstrap.os, "execve") as launch:
                    with self.assertRaises(bootstrap.BootstrapError) as error:
                        bootstrap.start(self.profile())
                    self.assertNotIn(FAKE_TOKEN, str(error.exception))
                    launch.assert_not_called()

    def test_no_scope_or_profile_overrides(self):
        with patch.object(bootstrap, "start") as start:
            with self.assertRaises(bootstrap.BootstrapError):
                bootstrap.main(["--project=other"])
            start.assert_not_called()

    def test_private_ca_mismatch_fails_before_native_proxy_start(self):
        responses = [
            subprocess.CompletedProcess([], 0, FAKE_TOKEN, ""),
            subprocess.CompletedProcess([], 0, FAKE_KEY + "changed", ""),
        ]
        with patch.object(bootstrap.subprocess, "run", side_effect=responses):
            with patch.object(bootstrap.os, "execve") as launch:
                with self.assertRaises(bootstrap.BootstrapError) as error:
                    bootstrap.start(self.profile())
                self.assertNotIn(FAKE_KEY, str(error.exception))
                launch.assert_not_called()

    def test_duplicate_metadata_keys_are_rejected(self):
        with self.assertRaises(bootstrap.BootstrapError):
            bootstrap.json_object([("version", 1), ("version", 1)])

    def test_metadata_checks_explicit_source_scope_and_runtime_without_a_runner(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            root.chmod(0o700)
            cli = root / "infisical"
            cli.write_text("synthetic executable fixture")
            ca = root / "public-ca.pem"
            ca.write_text("synthetic public certificate fixture")
            project = "00000000-0000-4000-8000-000000000001"
            profile = root / "profile.json"
            p = {
                **self.profile(),
                "version": 1,
                "instance": bootstrap.INSTANCE,
                "environment": "dev",
                "secret_path": "/proxy",
                "secret_name": bootstrap.SOURCE_SECRET,
                "proxy_id": project,
                "port": 8283,
                "infisical": str(cli),
                "cli_sha256": bootstrap.digest(cli),
                "self_sha256": bootstrap.digest(Path(bootstrap.__file__)),
                "ca_fingerprint": "SHA256:"
                + ":".join(
                    [
                        hashlib.sha256(b"fake-der").hexdigest().upper()[i : i + 2]
                        for i in range(0, 64, 2)
                    ]
                ),
                "ca_file": str(ca),
                "ca_file_sha256": bootstrap.digest(ca),
            }
            profile.write_text(json.dumps(p))
            profile.chmod(0o600)
            with (
                patch.object(bootstrap, "CLI", cli),
                patch.object(bootstrap.ssl, "PEM_cert_to_DER_cert", return_value=b"fake-der"),
                patch.object(bootstrap.subprocess, "run", side_effect=AssertionError("No runner or provider call during metadata validation")),
            ):
                self.assertEqual(bootstrap.load(profile), p)
                for delta in [
                    {"secret_path": "/runtime"},
                    {"environment": "prod"},
                    {"extra": "unreviewed"},
                    {"runbox_archive": "unreviewed"},
                    {"version": True},
                    {"cli_sha256": "0" * 64},
                    {"self_sha256": "0" * 64},
                ]:
                    profile.write_text(json.dumps({**p, **delta}))
                    with self.assertRaises(bootstrap.BootstrapError):
                        bootstrap.load(profile)


if __name__ == "__main__":
    unittest.main()
