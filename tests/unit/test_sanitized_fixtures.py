import json
from pathlib import Path
import re
import unittest

from linode_backup_lab.config import BackupLabConfig, TargetConfig, load_config
from linode_backup_lab.inspect import create_inspect_manifest


REPO_ROOT = Path(__file__).resolve().parents[2]
SANITIZED_FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "sanitized"


class SanitizedFixtureClient:
    provider_api_version = "v4"

    def __init__(self, backups: list[dict[str, object]]) -> None:
        self.backups = backups

    def list_backups(self, linode_id: int) -> list[dict[str, object]]:
        return self.backups


def load_json_fixture(name: str) -> object:
    return json.loads((SANITIZED_FIXTURE_DIR / name).read_text(encoding="utf-8"))


class SanitizedFixtureTests(unittest.TestCase):
    def test_example_config_loads_with_only_synthetic_values(self) -> None:
        config = load_config(REPO_ROOT / "examples" / "backup-lab.example.toml")

        self.assertEqual(config.schema_version, "1")
        self.assertEqual(config.target.linode_id, 1)
        self.assertEqual(config.target.snapshot_label, "example-snapshot")

    def test_sanitized_provider_fixture_generates_expected_report_fixture(self) -> None:
        backups = load_json_fixture("inspect-provider-backups.normalized.json")
        self.assertIsInstance(backups, list)

        config = BackupLabConfig(
            schema_version="1",
            target=TargetConfig(linode_id=1, snapshot_label="SANITIZED_SNAPSHOT_LABEL"),
        )
        report = create_inspect_manifest(
            config,
            client=SanitizedFixtureClient(backups),
            run_id="sanitized-inspect-report",
            created_at="not-recorded",
        )

        self.assertEqual(report, load_json_fixture("inspect-report.match.json"))

        report_json = json.dumps(report, sort_keys=True)
        self.assertNotIn("SANITIZED_BACKUP_ID_AUTOMATIC", report_json)
        self.assertNotIn("SANITIZED_BACKUP_ID_SNAPSHOT", report_json)
        self.assertNotIn("SANITIZED_SNAPSHOT_LABEL", report_json)
        self.assertNotIn("SANITIZED_PROVIDER_TIMESTAMP", report_json)

    def test_sanitized_fixtures_avoid_private_or_raw_provider_material(self) -> None:
        fixture_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted(SANITIZED_FIXTURE_DIR.rglob("*"))
            if path.is_file()
        )

        self.assertNotRegex(fixture_text, r"\d{4}-\d{2}-\d{2}T\d{2}:")
        self.assertNotRegex(fixture_text, r"\b\d{6,}\b")
        self.assertNotIn("Authorization", fixture_text)
        self.assertNotIn("Bearer ", fixture_text)
        self.assertNotIn("LINODE_TOKEN", fixture_text)
        self.assertNotIn("https://", fixture_text)


if __name__ == "__main__":
    unittest.main()
