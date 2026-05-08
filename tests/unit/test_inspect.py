import json
import unittest

from linode_backup_lab.config import BackupLabConfig, TargetConfig
from linode_backup_lab.inspect import create_inspect_manifest


class FakeInspectClient:
    provider_api_version = "v4beta"

    def __init__(self) -> None:
        self.seen_linode_ids: list[int] = []

    def list_backups(self, linode_id: int) -> list[dict[str, object]]:
        self.seen_linode_ids.append(linode_id)
        return [
            {
                "backup_id": 987654,
                "backup_label": None,
                "backup_status": "successful",
                "backup_kind": "automatic",
                "snapshot_state": None,
                "provider_type": "auto",
                "available": True,
                "created_at": "2026-05-06T12:00:00",
                "finished_at": "2026-05-06T12:05:00",
                "updated_at": "2026-05-06T12:06:00",
                "config_count": 1,
                "disk_count": 2,
            },
            {
                "backup_id": 123456,
                "backup_label": "private-manual-label",
                "backup_status": "running",
                "backup_kind": "snapshot",
                "snapshot_state": "in_progress",
                "provider_type": "snapshot",
                "available": False,
                "created_at": "2026-05-06T13:00:00",
                "finished_at": None,
                "updated_at": "2026-05-06T13:01:00",
                "config_count": 1,
                "disk_count": 2,
            },
        ]


class InspectTests(unittest.TestCase):
    def test_inspect_manifest_reads_provider_and_redacts_public_output(self) -> None:
        config = BackupLabConfig(
            schema_version="1",
            target=TargetConfig(linode_id=112233, snapshot_label="private-target-label"),
        )
        client = FakeInspectClient()

        manifest = create_inspect_manifest(
            config,
            client=client,
            run_id="inspect-test",
            created_at="2026-05-06T00:00:00+00:00",
        )
        manifest_json = json.dumps(manifest, sort_keys=True)

        self.assertEqual(client.seen_linode_ids, [112233])
        self.assertEqual(manifest["run_id"], "inspect-test")
        self.assertEqual(manifest["status"], "inspected")
        self.assertEqual(manifest["provider"], {"name": "linode", "api_version": "v4beta"})
        self.assertEqual(manifest["config"], {"schema_version": "1"})
        self.assertEqual(
            manifest["command"]["provider_calls"],
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
        self.assertEqual(manifest["provider_read"]["method"], "GET")
        self.assertEqual(manifest["provider_read"]["status"], "performed")
        self.assertEqual(
            manifest["mutation_intent"],
            {
                "planned_operation": None,
                "execution_requested": False,
                "execution_allowed": False,
                "execution_performed": False,
                "reason": "read-only inspection only",
            },
        )
        self.assertEqual(manifest["outcome"]["status"], "provider_read_completed")
        self.assertEqual(manifest["outcome"]["provider_reads"][0]["response_received"], True)
        self.assertNotIn("provider_read_completed", manifest["validation"]["checks"])
        self.assertEqual(manifest["safety"]["provider_mutations"], "not_performed")
        self.assertIs(manifest["safety"]["read_only_enforced"], True)
        self.assertEqual(manifest["inspection_summary"]["backup_count"], 2)
        self.assertEqual(manifest["inspection_summary"]["status_counts"], {"running": 1, "successful": 1})
        self.assertIs(manifest["inspection_summary"]["snapshot_in_progress_present"], True)
        self.assertEqual(
            manifest["review"],
            {
                "provider_calls": {
                    "occurred": True,
                    "total": 1,
                    "by_kind": {"read": 1},
                    "operations": ["list_backups"],
                },
                "mutations": {
                    "planned_operation": None,
                    "execution_requested": False,
                    "execution_allowed": False,
                    "execution_performed": False,
                    "provider_mutations": "not_performed",
                    "skipped_reason": "read_only_inspection",
                },
                "state_visibility": {
                    "provider_backup_state": "read",
                    "skipped_states": ["provider_mutation"],
                    "unknown_fields": {
                        "available": 0,
                        "backup_kind": 0,
                        "backup_status": 0,
                        "config_count": 0,
                        "disk_count": 0,
                        "provider_type": 0,
                        "snapshot_state_for_snapshot": 0,
                    },
                },
            },
        )
        self.assertEqual(manifest["normalized_backup_state"][0]["disk_count"], 2)
        self.assertEqual(manifest["normalized_backup_state"][0]["backup_id"]["validated_as"], "provider_backup_id")
        self.assertNotIn("112233", manifest_json)
        self.assertNotIn("private-target-label", manifest_json)
        self.assertNotIn("987654", manifest_json)
        self.assertNotIn("private-manual-label", manifest_json)
        self.assertNotIn("2026-05-06T13:00:00", manifest_json)

    def test_inspect_manifest_names_documented_provider_fields_separately(self) -> None:
        config = BackupLabConfig(
            schema_version="1",
            target=TargetConfig(linode_id=123, snapshot_label="pre-upgrade"),
        )

        manifest = create_inspect_manifest(config, client=FakeInspectClient())

        self.assertIn("status", manifest["provider_documented_fields"]["backup_record"])
        self.assertIn("snapshot.current", manifest["provider_documented_fields"]["collection"])
        self.assertIn("normalized_backup_state", manifest)

    def test_inspect_review_counts_unknown_normalized_state(self) -> None:
        class UnknownStateClient:
            provider_api_version = "v4"

            def list_backups(self, linode_id: int) -> list[dict[str, object]]:
                return [
                    {
                        "backup_id": None,
                        "backup_label": None,
                        "backup_status": None,
                        "backup_kind": "snapshot",
                        "snapshot_state": None,
                        "provider_type": None,
                        "available": None,
                        "created_at": None,
                        "finished_at": None,
                        "updated_at": None,
                        "config_count": None,
                        "disk_count": None,
                    }
                ]

        config = BackupLabConfig(
            schema_version="1",
            target=TargetConfig(linode_id=123, snapshot_label="pre-upgrade"),
        )

        manifest = create_inspect_manifest(config, client=UnknownStateClient())

        self.assertEqual(
            manifest["review"]["state_visibility"]["unknown_fields"],
            {
                "available": 1,
                "backup_kind": 0,
                "backup_status": 1,
                "config_count": 1,
                "disk_count": 1,
                "provider_type": 1,
                "snapshot_state_for_snapshot": 1,
            },
        )


if __name__ == "__main__":
    unittest.main()
