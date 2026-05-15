import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from linode_backup_lab.config import BackupLabConfig, TargetConfig, load_config
from linode_backup_lab.inspect import create_inspect_manifest
from linode_backup_lab.replay import create_replay_inspect_manifest, load_sanitized_inspect_fixture


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

    def test_sanitized_provider_fixture_generates_public_safe_report_shape(self) -> None:
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

        self.assertLessEqual(
            {
                "command",
                "inspection_summary",
                "normalized_backup_state",
                "outcome",
                "provider_read",
                "review",
                "safety",
                "state_assessment",
            },
            set(report),
        )
        self.assertEqual(report["action"], "inspect")
        self.assertEqual(report["status"], "inspected")
        self.assertIs(report["dry_run"], False)
        self.assertEqual(report["provider"], {"name": "linode", "api_version": "v4"})

        self.assertEqual(
            report["command"]["provider_calls"],
            {
                "occurred": True,
                "items": [
                    {
                        "kind": "read",
                        "method": "GET",
                        "operation": "list_backups",
                    }
                ],
            },
        )
        self.assertEqual(
            report["review"]["provider_calls"],
            {
                "occurred": True,
                "total": 1,
                "by_kind": {"read": 1},
                "operations": ["list_backups"],
            },
        )
        self.assertEqual(report["provider_read"]["status"], "performed")
        self.assertEqual(report["provider_read"]["operation"], "list_backups")
        self.assertIs(report["provider_read"]["raw_response_recorded"], False)

        self.assertIsNone(report["mutation_intent"]["planned_operation"])
        self.assertIs(report["mutation_intent"]["execution_requested"], False)
        self.assertIs(report["mutation_intent"]["execution_allowed"], False)
        self.assertIs(report["mutation_intent"]["execution_performed"], False)
        self.assertEqual(report["review"]["mutations"]["provider_mutations"], "not_performed")
        self.assertEqual(report["outcome"]["execution_state"], "completed")
        self.assertEqual(report["outcome"]["retry_classification"], "safe_to_rerun_read_only")
        self.assertEqual(report["outcome"]["provider_mutations"], [])
        self.assertEqual(report["safety"]["provider_reads"], "performed")
        self.assertEqual(report["safety"]["provider_mutations"], "not_performed")
        self.assertIs(report["safety"]["linode_token_recorded"], False)
        self.assertIs(report["safety"]["read_only_enforced"], True)

        self.assertEqual(report["inspection_summary"]["backup_count"], 2)
        self.assertEqual(report["inspection_summary"]["automatic_backup_count"], 1)
        self.assertIs(report["inspection_summary"]["snapshot_current_present"], True)
        self.assertIs(report["inspection_summary"]["snapshot_in_progress_present"], False)
        self.assertEqual(report["inspection_summary"]["status_counts"], {"successful": 2})
        self.assertEqual(report["state_assessment"]["status"], "provider_local_match")
        self.assertEqual(report["state_assessment"]["provider_local_match"], "matched")

        backup_state = report["normalized_backup_state"]
        self.assertEqual(len(backup_state), 2)
        self.assert_backup_state_subset(
            backup_state[0],
            backup_kind="automatic",
            snapshot_state=None,
            provider_type="auto",
            backup_status="successful",
        )
        self.assert_backup_state_subset(
            backup_state[1],
            backup_kind="snapshot",
            snapshot_state="current",
            provider_type="snapshot",
            backup_status="successful",
        )
        self.assertEqual(
            report["review"]["state_visibility"]["unknown_fields"],
            {
                "available": 0,
                "backup_kind": 0,
                "backup_status": 0,
                "config_count": 0,
                "disk_count": 0,
                "provider_type": 0,
                "snapshot_state_for_snapshot": 0,
            },
        )

        report_json = json.dumps(report, sort_keys=True)
        self.assertNotIn("SANITIZED_BACKUP_ID_AUTOMATIC", report_json)
        self.assertNotIn("SANITIZED_BACKUP_ID_SNAPSHOT", report_json)
        self.assertNotIn("SANITIZED_SNAPSHOT_LABEL", report_json)
        self.assertNotIn("SANITIZED_PROVIDER_TIMESTAMP", report_json)

    def test_sanitized_provider_fixture_replays_without_provider_or_credentials(self) -> None:
        backups = load_sanitized_inspect_fixture(SANITIZED_FIXTURE_DIR / "inspect-provider-backups.normalized.json")

        config = BackupLabConfig(
            schema_version="1",
            target=TargetConfig(linode_id=1, snapshot_label="SANITIZED_SNAPSHOT_LABEL"),
        )
        report = create_replay_inspect_manifest(
            config,
            fixture_backups=backups,
            run_id="sanitized-inspect-replay",
            created_at="not-recorded",
        )

        self.assertEqual(report["action"], "inspect-replay")
        self.assertEqual(report["status"], "replayed")
        self.assertIs(report["dry_run"], True)
        self.assertEqual(report["command"]["token_source"], "not_required")
        self.assertEqual(report["command"]["fixture_source"], "explicit")
        self.assertEqual(report["command"]["provider_calls"], {"occurred": False, "items": []})
        self.assertEqual(report["provider_read"]["status"], "not_performed")
        self.assertEqual(report["provider_read"]["replay_source"], "sanitized_fixture")
        self.assertEqual(report["fixture_replay"]["source"], "sanitized_fixture")
        self.assertIs(report["fixture_replay"]["provider_credentials_required"], False)
        self.assertIs(report["fixture_replay"]["live_provider_state_read"], False)
        self.assertIs(report["fixture_replay"]["provider_currentness_asserted"], False)
        self.assertEqual(report["review"]["state_visibility"]["provider_backup_state"], "fixture_replay")
        self.assertEqual(report["review"]["retry_recovery"]["provider_state_classification"], "refresh_before_retry")
        self.assertEqual(report["state_assessment"]["status"], "fixture_replayed")
        self.assertEqual(report["state_assessment"]["source"], "sanitized_fixture_replay")
        self.assertIs(report["state_assessment"]["provider_read_performed"], False)
        self.assertIs(report["state_assessment"]["fixture_local_match"], True)
        self.assertIs(report["state_assessment"]["refresh_before_mutation"]["required"], True)
        self.assertEqual(report["safety"]["credentials"], "not_required")
        self.assertIs(report["safety"]["linode_token_required"], False)
        self.assertEqual(report["safety"]["provider_reads"], "not_performed")
        self.assertIs(report["safety"]["fixture_replay_only"], True)

        report_json = json.dumps(report, sort_keys=True)
        self.assertNotIn("SANITIZED_BACKUP_ID_AUTOMATIC", report_json)
        self.assertNotIn("SANITIZED_BACKUP_ID_SNAPSHOT", report_json)
        self.assertNotIn("SANITIZED_SNAPSHOT_LABEL", report_json)
        self.assertNotIn("SANITIZED_PROVIDER_TIMESTAMP", report_json)

    def test_expanded_sanitized_fixture_corpus_replays_edge_cases(self) -> None:
        cases = [
            (
                "inspect-provider-backups.status-transitions.normalized.json",
                "SANITIZED_SNAPSHOT_LABEL_CURRENT",
                {
                    "backup_count": 3,
                    "automatic_backup_count": 1,
                    "snapshot_current_present": True,
                    "snapshot_in_progress_present": True,
                    "available_backup_count": 2,
                    "status_counts": {"running": 1, "successful": 2},
                },
                {
                    "available": 0,
                    "backup_kind": 0,
                    "backup_status": 0,
                    "config_count": 0,
                    "disk_count": 0,
                    "provider_type": 0,
                    "snapshot_state_for_snapshot": 0,
                },
                {
                    "fixture_local_match": None,
                    "snapshot_current_present": True,
                    "snapshot_in_progress_present": True,
                },
            ),
            (
                "inspect-provider-backups.missing-optional-fields.normalized.json",
                "SANITIZED_SNAPSHOT_LABEL_SPARSE",
                {
                    "backup_count": 2,
                    "automatic_backup_count": 1,
                    "snapshot_current_present": False,
                    "snapshot_in_progress_present": False,
                    "available_backup_count": 0,
                    "status_counts": {},
                },
                {
                    "available": 2,
                    "backup_kind": 0,
                    "backup_status": 2,
                    "config_count": 2,
                    "disk_count": 2,
                    "provider_type": 2,
                    "snapshot_state_for_snapshot": 1,
                },
                {
                    "fixture_local_match": None,
                    "snapshot_current_present": False,
                    "snapshot_in_progress_present": False,
                },
            ),
        ]

        for fixture_name, snapshot_label, expected_summary, expected_unknowns, expected_state in cases:
            with self.subTest(fixture_name=fixture_name):
                backups = load_sanitized_inspect_fixture(SANITIZED_FIXTURE_DIR / fixture_name)
                config = BackupLabConfig(
                    schema_version="1",
                    target=TargetConfig(linode_id=1, snapshot_label=snapshot_label),
                )
                report = create_replay_inspect_manifest(
                    config,
                    fixture_backups=backups,
                    run_id="sanitized-expanded-fixture-replay",
                    created_at="not-recorded",
                )

                self.assertEqual(report["action"], "inspect-replay")
                self.assertEqual(report["status"], "replayed")
                self.assertEqual(report["command"]["provider_calls"], {"occurred": False, "items": []})
                self.assertEqual(report["provider_read"]["status"], "not_performed")
                self.assertEqual(report["fixture_replay"]["source"], "sanitized_fixture")
                self.assertEqual(
                    {key: value for key, value in report["inspection_summary"].items() if key != "target"},
                    expected_summary,
                )
                self.assertEqual(report["review"]["state_visibility"]["unknown_fields"], expected_unknowns)
                for key, value in expected_state.items():
                    self.assertEqual(report["state_assessment"][key], value)
                self.assertEqual(report["state_assessment"]["status"], "fixture_replayed")
                self.assertTrue(report["state_assessment"]["refresh_before_mutation"]["required"])
                self.assertEqual(report["review"]["retry_recovery"]["provider_state_classification"], "refresh_before_retry")

                report_json = json.dumps(report, sort_keys=True)
                self.assertNotIn("SANITIZED_BACKUP_ID", report_json)
                self.assertNotIn("SANITIZED_SNAPSHOT_LABEL", report_json)
                self.assertNotIn("SANITIZED_PROVIDER_TIMESTAMP", report_json)

    def test_all_sanitized_fixture_files_load_as_replay_safe_normalized_arrays(self) -> None:
        fixture_paths = sorted(SANITIZED_FIXTURE_DIR.glob("*.normalized.json"))
        self.assertGreaterEqual(len(fixture_paths), 3)

        for fixture_path in fixture_paths:
            with self.subTest(fixture=fixture_path.name):
                backups = load_sanitized_inspect_fixture(fixture_path)

                self.assertIsInstance(backups, list)
                self.assertTrue(all(isinstance(backup, dict) for backup in backups))
                raw_provider_keys = {"id", "label", "created", "finished", "updated", "configs", "disks"}
                self.assertTrue(all(not (raw_provider_keys & set(backup)) for backup in backups))

    def test_replay_fixture_loader_rejects_unsanitized_sensitive_normalized_values(self) -> None:
        with TemporaryDirectory() as tmpdir:
            fixture_path = Path(tmpdir) / "unsafe-normalized.json"
            fixture_path.write_text(
                json.dumps(
                    [
                        {
                            "backup_id": "SANITIZED_BACKUP_ID",
                            "backup_label": "private-snapshot-label",
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

            with self.assertRaisesRegex(ValueError, "backup_label must use a sanitized placeholder"):
                load_sanitized_inspect_fixture(fixture_path)

    def test_replay_fixture_loader_rejects_raw_provider_shape_and_urls(self) -> None:
        with TemporaryDirectory() as tmpdir:
            raw_shape_path = Path(tmpdir) / "raw-provider-shape.json"
            raw_shape_path.write_text(
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
                encoding="utf-8",
            )
            raw_url_path = Path(tmpdir) / "raw-url.json"
            raw_url_path.write_text(
                json.dumps(
                    [
                        {
                            "backup_id": "SANITIZED_BACKUP_ID",
                            "backup_label": None,
                            "provider_note": "https://api.linode.com/v4/linode/instances/123456/backups",
                        }
                    ]
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "contains raw provider fields"):
                load_sanitized_inspect_fixture(raw_shape_path)
            with self.assertRaisesRegex(ValueError, "unsafe raw-looking fixture text"):
                load_sanitized_inspect_fixture(raw_url_path)

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

    def assert_backup_state_subset(
        self,
        backup: dict[str, object],
        *,
        backup_kind: str,
        snapshot_state: str | None,
        provider_type: str,
        backup_status: str,
    ) -> None:
        self.assertEqual(backup["backup_kind"], backup_kind)
        self.assertEqual(backup["snapshot_state"], snapshot_state)
        self.assertEqual(backup["provider_type"], provider_type)
        self.assertEqual(backup["backup_status"], backup_status)
        self.assertIs(backup["available"], True)
        self.assertEqual(backup["config_count"], 1)
        self.assertEqual(backup["disk_count"], 1)
        self.assert_redacted_field(backup["backup_id"], "provider_backup_id")
        self.assert_redacted_field(backup["created_at"], "provider_timestamp")
        self.assert_redacted_field(backup["finished_at"], "provider_timestamp")
        self.assert_redacted_field(backup["updated_at"], "provider_timestamp")
        label = backup["backup_label"]
        if snapshot_state is None:
            self.assertEqual(
                label,
                {
                    "present": False,
                    "redacted": False,
                    "validated_as": "not_present",
                },
            )
        else:
            self.assert_redacted_field(label, "provider_label")

    def assert_redacted_field(self, field: dict[str, object], validated_as: str) -> None:
        self.assertIs(field["present"], True)
        self.assertIs(field["redacted"], True)
        self.assertEqual(field["validated_as"], validated_as)


if __name__ == "__main__":
    unittest.main()
