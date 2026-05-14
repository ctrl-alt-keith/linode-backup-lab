from contextlib import redirect_stderr
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

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
    def test_plan_requires_explicit_config_path(self) -> None:
        parser = build_parser()
        stderr = StringIO()

        with redirect_stderr(stderr), self.assertRaises(SystemExit) as raised:
            parser.parse_args(["plan"])

        self.assertEqual(raised.exception.code, 2)
        self.assertIn("--config", stderr.getvalue())

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


if __name__ == "__main__":
    unittest.main()
