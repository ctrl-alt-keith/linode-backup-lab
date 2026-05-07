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


if __name__ == "__main__":
    unittest.main()
