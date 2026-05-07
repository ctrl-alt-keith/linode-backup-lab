from contextlib import redirect_stderr
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from linode_backup_lab.cli import build_parser, main


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
            stdout = StringIO()
            stderr = StringIO()

            exit_code = main(["plan", "--config", str(path)], stdout=stdout, stderr=stderr)

        manifest = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertIs(manifest["dry_run"], True)
        self.assertEqual(manifest["command"]["config_source"], "explicit")
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


if __name__ == "__main__":
    unittest.main()
