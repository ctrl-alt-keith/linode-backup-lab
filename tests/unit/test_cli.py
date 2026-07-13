from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from linode_backup_lab.cli import build_parser, main
from linode_backup_lab.linode_api import ProviderError


def write_config(path: Path) -> None:
    path.write_text(
        '\n'.join(
            [
                'schema_version = "1"',
                "",
                "[target]",
                "linode_id = 123",
                'snapshot_label = "pre-upgrade"',
            ]
        ),
        encoding="utf-8",
    )


class FakeInspectClient:
    provider_api_version = "v4"

    def __init__(self, token: str) -> None:
        self.token = token

    def list_backups(self, linode_id: int) -> list[dict[str, object]]:
        return [
            {
                "backup_id": 987,
                "backup_label": "private-label",
                "backup_status": "successful",
                "backup_kind": "snapshot",
                "snapshot_state": "current",
                "provider_type": "snapshot",
                "available": True,
                "created_at": "2026-05-06T12:00:00",
                "finished_at": "2026-05-06T12:05:00",
                "updated_at": "2026-05-06T12:06:00",
                "config_count": 1,
                "disk_count": 2,
            }
        ]


class FailingInspectClient:
    provider_api_version = "v4beta"

    def __init__(self, token: str) -> None:
        self.token = token

    def list_backups(self, linode_id: int) -> list[dict[str, object]]:
        raise ProviderError(
            f"raw provider detail token={self.token} linode={linode_id} label=pre-upgrade",
            public_message="Linode API returned invalid JSON",
            category="invalid_json",
            request_sent=True,
            response_received=True,
        )


class CliTests(unittest.TestCase):
    def test_version_prints_package_version_and_exits(self) -> None:
        output = StringIO()

        with patch("linode_backup_lab.cli.version", return_value="9.8.7") as package_version:
            with redirect_stdout(output), self.assertRaises(SystemExit) as raised:
                main(["--version"])

        self.assertEqual(raised.exception.code, 0)
        self.assertEqual(output.getvalue(), "9.8.7\n")
        package_version.assert_called_once_with("linode-backup-lab")

    def test_version_after_subcommand_prints_package_version_and_exits(self) -> None:
        for command in ("config-check", "plan", "inspect", "inspect-replay"):
            with self.subTest(command=command):
                output = StringIO()

                with patch("linode_backup_lab.cli.version", return_value="9.8.7"):
                    with redirect_stdout(output), self.assertRaises(SystemExit) as raised:
                        main([command, "--version"])

                self.assertEqual(raised.exception.code, 0)
                self.assertEqual(output.getvalue(), "9.8.7\n")

    def test_help_output_includes_version_flag(self) -> None:
        with patch("linode_backup_lab.cli.version", return_value="9.8.7"):
            help_output = build_parser().format_help()

        self.assertIn("--version", help_output)

    def test_plan_requires_explicit_config_path(self) -> None:
        parser = build_parser()
        stderr = StringIO()

        with redirect_stderr(stderr), self.assertRaises(SystemExit) as raised:
            parser.parse_args(["plan"])

        self.assertEqual(raised.exception.code, 2)
        self.assertIn("--config", stderr.getvalue())

    def test_config_check_requires_explicit_config_path(self) -> None:
        parser = build_parser()
        stderr = StringIO()

        with redirect_stderr(stderr), self.assertRaises(SystemExit) as raised:
            parser.parse_args(["config-check"])

        self.assertEqual(raised.exception.code, 2)
        self.assertIn("--config", stderr.getvalue())

    def test_config_check_outputs_public_safe_validation_manifest(self) -> None:
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "backup-lab.toml"
            write_config(path)
            stdout = StringIO()
            stderr = StringIO()

            exit_code = main(["config-check", "--config", str(path)], stdout=stdout, stderr=stderr, environ={})

        manifest_json = stdout.getvalue()
        manifest = json.loads(manifest_json)
        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(manifest["action"], "config-check")
        self.assertEqual(manifest["status"], "valid")
        self.assertIs(manifest["dry_run"], True)
        self.assertEqual(manifest["command"]["config_source"], "explicit")
        self.assertEqual(manifest["command"]["provider_calls"], {"occurred": False, "items": []})
        self.assertEqual(manifest["validation"]["status"], "passed")
        self.assertIn("provider_state_not_checked", manifest["validation"]["checks"])
        self.assertEqual(manifest["safety"]["credentials"], "not_required")
        self.assertIs(manifest["safety"]["linode_token_required"], False)
        self.assertEqual(manifest["safety"]["provider_reads"], "not_performed")
        self.assertEqual(manifest["safety"]["provider_mutations"], "not_performed")
        self.assertNotIn("123", manifest_json)
        self.assertNotIn("pre-upgrade", manifest_json)

    def test_plan_outputs_dry_run_manifest(self) -> None:
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "backup-lab.toml"
            write_config(path)
            stdout = StringIO()
            stderr = StringIO()

            exit_code = main(["plan", "--config", str(path)], stdout=stdout, stderr=stderr)

        manifest = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertIs(manifest["dry_run"], True)
        self.assertEqual(manifest["command"]["config_source"], "explicit")
        self.assertEqual(manifest["command"]["provider_calls"], {"occurred": False, "items": []})
        self.assertEqual(manifest["safety"]["provider_mutations"], "not_performed")

    def test_invalid_config_returns_error_without_manifest(self) -> None:
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "backup-lab.toml"
            path.write_text('schema_version = "2"\n', encoding="utf-8")
            stdout = StringIO()
            stderr = StringIO()

            exit_code = main(["plan", "--config", str(path)], stdout=stdout, stderr=stderr)

        self.assertEqual(exit_code, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("unsupported config schema_version", stderr.getvalue())
        self.assertIn(str(path), stderr.getvalue())
        self.assertIn("hint: Set schema_version", stderr.getvalue())

    def test_invalid_config_cli_groups_local_validation_errors(self) -> None:
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "backup-lab.toml"
            path.write_text(
                '\n'.join(
                    [
                        'schema_version = "2"',
                        "",
                        "[target]",
                        "linode_id = false",
                        'snapshot_label = ""',
                    ]
                ),
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            exit_code = main(["plan", "--config", str(path)], stdout=stdout, stderr=stderr)

        error_text = stderr.getvalue()
        self.assertEqual(exit_code, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("3 validation issues", error_text)
        self.assertIn("schema_version", error_text)
        self.assertIn("target.linode_id", error_text)
        self.assertIn("target.snapshot_label", error_text)
        self.assertIn("hint:", error_text)

    def test_unknown_command_is_rejected_before_dispatch(self) -> None:
        parser = build_parser()
        stderr = StringIO()

        with redirect_stderr(stderr), self.assertRaises(SystemExit) as raised:
            parser.parse_args(["snapshot", "--config", "backup-lab.toml"])

        self.assertEqual(raised.exception.code, 2)
        self.assertIn("invalid choice", stderr.getvalue())

    def test_restore_command_is_not_implemented(self) -> None:
        parser = build_parser()
        stderr = StringIO()

        with redirect_stderr(stderr), self.assertRaises(SystemExit) as raised:
            parser.parse_args(["restore", "--config", "backup-lab.toml"])

        self.assertEqual(raised.exception.code, 2)
        self.assertIn("invalid choice", stderr.getvalue())

    def test_inspect_requires_explicit_config_path(self) -> None:
        parser = build_parser()
        stderr = StringIO()

        with redirect_stderr(stderr), self.assertRaises(SystemExit) as raised:
            parser.parse_args(["inspect"])

        self.assertEqual(raised.exception.code, 2)
        self.assertIn("--config", stderr.getvalue())

    def test_inspect_replay_requires_explicit_config_and_fixture_paths(self) -> None:
        parser = build_parser()
        stderr = StringIO()

        with redirect_stderr(stderr), self.assertRaises(SystemExit) as raised:
            parser.parse_args(["inspect-replay"])

        self.assertEqual(raised.exception.code, 2)
        self.assertIn("--config", stderr.getvalue())
        self.assertIn("--fixture", stderr.getvalue())

    def test_inspect_replay_invalid_fixture_returns_precondition_error_without_manifest(self) -> None:
        cases = [
            ("malformed-json", "{not json", "inspect replay fixture is not valid JSON"),
            (
                "raw-provider-shape",
                json.dumps(
                    [
                        {
                            "id": 123456,
                            "label": "private-snapshot-label",
                            "status": "successful",
                            "type": "snapshot",
                        }
                    ]
                ),
                "contains raw provider fields",
            ),
        ]

        for name, fixture_text, expected_error in cases:
            with self.subTest(name=name):
                with TemporaryDirectory() as tmpdir:
                    config_path = Path(tmpdir) / "backup-lab.toml"
                    write_config(config_path)
                    fixture_path = Path(tmpdir) / f"{name}.json"
                    fixture_path.write_text(fixture_text, encoding="utf-8")
                    stdout = StringIO()
                    stderr = StringIO()

                    exit_code = main(
                        ["inspect-replay", "--config", str(config_path), "--fixture", str(fixture_path)],
                        stdout=stdout,
                        stderr=stderr,
                        environ={},
                    )

                self.assertEqual(exit_code, 2)
                self.assertEqual(stdout.getvalue(), "")
                self.assertIn(expected_error, stderr.getvalue())
                self.assertNotIn("private-snapshot-label", stderr.getvalue())
                self.assertNotIn("123456", stderr.getvalue())

    def test_inspect_requires_linode_token_from_environment(self) -> None:
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "backup-lab.toml"
            write_config(path)
            stdout = StringIO()
            stderr = StringIO()

            exit_code = main(["inspect", "--config", str(path)], stdout=stdout, stderr=stderr, environ={})

        self.assertEqual(exit_code, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("LINODE_TOKEN is required for inspect", stderr.getvalue())

    def test_inspect_outputs_public_safe_read_only_manifest(self) -> None:
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "backup-lab.toml"
            write_config(path)
            stdout = StringIO()
            stderr = StringIO()

            exit_code = main(
                ["inspect", "--config", str(path)],
                stdout=stdout,
                stderr=stderr,
                environ={"LINODE_TOKEN": "token-value"},
                inspect_client_factory=FakeInspectClient,
            )

        manifest_json = stdout.getvalue()
        manifest = json.loads(manifest_json)
        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(manifest["action"], "inspect")
        self.assertEqual(manifest["command"]["token_source"], "environment")
        self.assertEqual(manifest["command"]["provider_calls"]["items"][0]["operation"], "list_backups")
        self.assertEqual(manifest["provider_read"]["method"], "GET")
        self.assertEqual(manifest["safety"]["provider_mutations"], "not_performed")
        self.assertNotIn("token-value", manifest_json)
        self.assertNotIn("private-label", manifest_json)

    def test_inspect_provider_failure_preserves_exit_code_and_emits_safe_manifest(self) -> None:
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "backup-lab.toml"
            path.write_text(
                '\n'.join(
                    [
                        'schema_version = "1"',
                        "",
                        "[target]",
                        "linode_id = 112233",
                        'snapshot_label = "pre-upgrade"',
                    ]
                ),
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            exit_code = main(
                ["inspect", "--config", str(path)],
                stdout=stdout,
                stderr=stderr,
                environ={"LINODE_TOKEN": "token-value"},
                inspect_client_factory=FailingInspectClient,
            )

        manifest_json = stdout.getvalue()
        manifest = json.loads(manifest_json)
        self.assertEqual(exit_code, 1)
        self.assertIn("Linode API returned invalid JSON", stderr.getvalue())
        self.assertEqual(manifest["status"], "provider_read_failed")
        self.assertEqual(manifest["provider"], {"name": "linode", "api_version": "v4beta"})
        self.assertEqual(manifest["provider_read"]["failure"]["category"], "invalid_json")
        self.assertEqual(manifest["provider_read"]["failure"]["message"], "Linode API returned invalid JSON")
        self.assertEqual(
            manifest["outcome"]["retry_classification"],
            "safe_to_rerun_read_only_after_provider_failure",
        )
        self.assertEqual(manifest["safety"]["provider_reads"], "failed")
        self.assertNotIn("token-value", manifest_json)
        self.assertNotIn("pre-upgrade", manifest_json)
        self.assertNotIn("112233", manifest_json)
        self.assertNotIn("token-value", stderr.getvalue())
        self.assertNotIn("pre-upgrade", stderr.getvalue())

    def test_inspect_provider_setup_failure_does_not_claim_request_or_leak_details(self) -> None:
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "backup-lab.toml"
            path.write_text(
                '\n'.join(
                    [
                        'schema_version = "1"',
                        "",
                        "[target]",
                        "linode_id = 112233",
                        'snapshot_label = "pre-upgrade"',
                    ]
                ),
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            def failing_factory(token: str) -> FakeInspectClient:
                raise ProviderError(
                    f"raw setup detail token={token} linode=112233 label=pre-upgrade",
                    public_message="Linode provider client setup failed",
                    category="provider_setup_failed",
                    request_sent=False,
                    response_received=False,
                )

            exit_code = main(
                ["inspect", "--config", str(path)],
                stdout=stdout,
                stderr=stderr,
                environ={"LINODE_TOKEN": "token-value"},
                inspect_client_factory=failing_factory,
            )

        manifest_json = stdout.getvalue()
        manifest = json.loads(manifest_json)
        self.assertEqual(exit_code, 1)
        self.assertIn("Linode provider client setup failed", stderr.getvalue())
        self.assertEqual(manifest["status"], "provider_read_failed")
        self.assertEqual(manifest["provider"], {"name": "linode", "api_version": "v4"})
        self.assertEqual(manifest["command"]["provider_calls"], {"occurred": False, "items": []})
        self.assertEqual(manifest["provider_read"]["failure"]["category"], "provider_setup_failed")
        self.assertIs(manifest["provider_read"]["failure"]["request_sent"], False)
        self.assertIs(manifest["provider_read"]["failure"]["response_received"], False)
        self.assertIs(manifest["outcome"]["provider_reads"][0]["request_sent"], False)
        self.assertIs(manifest["outcome"]["provider_reads"][0]["response_received"], False)
        self.assertIs(manifest["state_assessment"]["provider_read_attempted"], False)
        self.assertNotIn("token-value", manifest_json)
        self.assertNotIn("pre-upgrade", manifest_json)
        self.assertNotIn("112233", manifest_json)
        self.assertNotIn("token-value", stderr.getvalue())
        self.assertNotIn("pre-upgrade", stderr.getvalue())
        self.assertNotIn("112233", stderr.getvalue())

    def test_inspect_replay_outputs_fixture_manifest_without_credentials_or_provider_reads(self) -> None:
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "backup-lab.toml"
            write_config(config_path)
            fixture_path = Path(tmpdir) / "backups.json"
            fixture_path.write_text(
                json.dumps(
                    [
                        {
                            "backup_id": "SANITIZED_BACKUP_ID",
                            "backup_label": "SANITIZED_SNAPSHOT_LABEL",
                            "backup_status": "successful",
                            "backup_kind": "snapshot",
                            "snapshot_state": "current",
                            "provider_type": "snapshot",
                            "available": True,
                            "created_at": "SANITIZED_PROVIDER_TIMESTAMP",
                            "finished_at": "SANITIZED_PROVIDER_TIMESTAMP",
                            "updated_at": "SANITIZED_PROVIDER_TIMESTAMP",
                            "config_count": 1,
                            "disk_count": 1,
                        }
                    ]
                ),
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            exit_code = main(
                ["inspect-replay", "--config", str(config_path), "--fixture", str(fixture_path)],
                stdout=stdout,
                stderr=stderr,
                environ={},
            )

        manifest_json = stdout.getvalue()
        manifest = json.loads(manifest_json)
        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(manifest["action"], "inspect-replay")
        self.assertIs(manifest["dry_run"], True)
        self.assertEqual(manifest["command"]["token_source"], "not_required")
        self.assertEqual(manifest["command"]["provider_calls"], {"occurred": False, "items": []})
        self.assertEqual(manifest["provider_read"]["status"], "not_performed")
        self.assertEqual(manifest["fixture_replay"]["source"], "sanitized_fixture")
        self.assertIs(manifest["fixture_replay"]["live_provider_state_read"], False)
        self.assertEqual(manifest["review"]["provider_calls"]["total"], 0)
        self.assertEqual(manifest["review"]["state_visibility"]["provider_backup_state"], "fixture_replay")
        self.assertEqual(manifest["state_assessment"]["source"], "sanitized_fixture_replay")
        self.assertIs(manifest["state_assessment"]["provider_read_performed"], False)
        self.assertEqual(
            manifest["review_summary"],
            {
                "headline": "inspect-replay: replayed; 1 backup; fixture_replayed",
                "provider_read": "not_performed",
                "state": {
                    "status": "fixture_replayed",
                    "provider_local_match": "not_evaluated_live",
                    "snapshot_current_present": True,
                    "snapshot_in_progress_present": False,
                    "refresh_before_mutation_required": True,
                },
                "backups": {
                    "total": 1,
                    "available": 1,
                    "automatic": 0,
                    "status_counts": [{"status": "successful", "count": 1}],
                },
                "attention": [
                    "Fixture replay is non-live and does not prove current provider state.",
                    "fixture replay is non-live and cannot prove current provider state",
                ],
            },
        )
        self.assertEqual(manifest["review"]["retry_recovery"]["provider_state_classification"], "refresh_before_retry")
        self.assertEqual(manifest["safety"]["credentials"], "not_required")
        self.assertIs(manifest["safety"]["linode_token_required"], False)
        self.assertEqual(manifest["safety"]["provider_reads"], "not_performed")
        self.assertIs(manifest["safety"]["fixture_replay_only"], True)
        self.assertNotIn("SANITIZED_BACKUP_ID", manifest_json)
        self.assertNotIn("SANITIZED_PROVIDER_TIMESTAMP", manifest_json)


if __name__ == "__main__":
    unittest.main()
