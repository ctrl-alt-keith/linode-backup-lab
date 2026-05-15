from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from linode_backup_lab.config import CONFIG_SCHEMA_VERSION, ConfigError, load_config


class ConfigTests(unittest.TestCase):
    def test_loads_minimal_explicit_config(self) -> None:
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "backup-lab.toml"
            path.write_text(
                '\n'.join(
                    [
                        f'schema_version = "{CONFIG_SCHEMA_VERSION}"',
                        "",
                        "[target]",
                        "linode_id = 123",
                        'snapshot_label = "pre-upgrade"',
                    ]
                ),
                encoding="utf-8",
            )

            config = load_config(path)

        self.assertEqual(config.schema_version, "1")
        self.assertEqual(config.target.linode_id, 123)
        self.assertEqual(config.target.snapshot_label, "pre-upgrade")

    def test_rejects_unsupported_schema_version(self) -> None:
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "backup-lab.toml"
            path.write_text(
                '\n'.join(
                    [
                        'schema_version = "2"',
                        "",
                        "[target]",
                        "linode_id = 123",
                        'snapshot_label = "pre-upgrade"',
                    ]
                ),
                encoding="utf-8",
            )

            with self.assertRaises(ConfigError):
                load_config(path)

    def test_rejects_hidden_or_unknown_keys(self) -> None:
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "backup-lab.toml"
            path.write_text(
                '\n'.join(
                    [
                        'schema_version = "1"',
                        "schedule = \"daily\"",
                        "",
                        "[target]",
                        "linode_id = 123",
                        'snapshot_label = "pre-upgrade"',
                    ]
                ),
                encoding="utf-8",
            )

            with self.assertRaises(ConfigError):
                load_config(path)

    def test_rejects_invalid_target_fields(self) -> None:
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "backup-lab.toml"
            path.write_text(
                '\n'.join(
                    [
                        'schema_version = "1"',
                        "",
                        "[target]",
                        "linode_id = 0",
                        'snapshot_label = " "',
                    ]
                ),
                encoding="utf-8",
            )

            with self.assertRaises(ConfigError):
                load_config(path)

    def test_reports_grouped_validation_failures_with_paths_and_hints(self) -> None:
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "backup-lab.toml"
            path.write_text(
                '\n'.join(
                    [
                        'schema_version = "2"',
                        'schedule = "daily"',
                        "",
                        "[target]",
                        "linode_id = 0",
                        'snapshot_label = " "',
                        'extra = "unsupported"',
                    ]
                ),
                encoding="utf-8",
            )

            with self.assertRaises(ConfigError) as raised:
                load_config(path)

        message = str(raised.exception)
        self.assertIn(f"invalid config {path}: 5 validation issues", message)
        self.assertIn("- <root>: unsupported config key(s): schedule", message)
        self.assertIn("- schema_version: unsupported config schema_version '2'; expected '1'", message)
        self.assertIn("- target: unsupported target key(s): extra", message)
        self.assertIn("- target.linode_id: target.linode_id must be a positive integer", message)
        self.assertIn(
            "- target.snapshot_label: target.snapshot_label must be a string with length 1..255",
            message,
        )
        self.assertIn("hint: Set schema_version", message)
        self.assertIn("hint: Set target.linode_id", message)

    def test_reports_missing_target_table_with_remediation_hint(self) -> None:
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "backup-lab.toml"
            path.write_text('schema_version = "1"\n', encoding="utf-8")

            with self.assertRaises(ConfigError) as raised:
                load_config(path)

        message = str(raised.exception)
        self.assertIn(f"invalid config {path}: 1 validation issue", message)
        self.assertIn("- target: config requires a [target] table", message)
        self.assertIn("hint: Add a [target] table with linode_id and snapshot_label.", message)

    def test_rejects_snapshot_label_longer_than_linode_create_snapshot_limit(self) -> None:
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "backup-lab.toml"
            path.write_text(
                '\n'.join(
                    [
                        'schema_version = "1"',
                        "",
                        "[target]",
                        "linode_id = 123",
                        f'snapshot_label = "{"x" * 256}"',
                    ]
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ConfigError, "length 1..255"):
                load_config(path)

    def test_accepts_snapshot_label_at_linode_create_snapshot_limit(self) -> None:
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "backup-lab.toml"
            snapshot_label = "x" * 255
            path.write_text(
                '\n'.join(
                    [
                        'schema_version = "1"',
                        "",
                        "[target]",
                        "linode_id = 123",
                        f'snapshot_label = "{snapshot_label}"',
                    ]
                ),
                encoding="utf-8",
            )

            config = load_config(path)

        self.assertEqual(config.target.snapshot_label, snapshot_label)


if __name__ == "__main__":
    unittest.main()
