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


class CurrentSnapshotClient:
    provider_api_version = "v4"

    def __init__(self, label: str | None) -> None:
        self.label = label

    def list_backups(self, linode_id: int) -> list[dict[str, object]]:
        return [
            {
                "backup_id": 123456,
                "backup_label": self.label,
                "backup_status": "successful",
                "backup_kind": "snapshot",
                "snapshot_state": "current",
                "provider_type": "snapshot",
                "available": True,
                "created_at": "2026-05-06T13:00:00",
                "finished_at": "2026-05-06T13:05:00",
                "updated_at": "2026-05-06T13:06:00",
                "config_count": 1,
                "disk_count": 2,
            }
        ]


class AmbiguousSnapshotClient:
    provider_api_version = "v4"

    def list_backups(self, linode_id: int) -> list[dict[str, object]]:
        return [
            {
                "backup_id": 222222,
                "backup_label": "private-target-label",
                "backup_status": "successful",
                "backup_kind": "snapshot",
                "snapshot_state": "current",
                "provider_type": "provider-added-snapshot-kind",
                "available": True,
                "created_at": "2026-05-06T13:00:00",
                "finished_at": "2026-05-06T13:05:00",
                "updated_at": "2026-05-06T13:06:00",
                "config_count": None,
                "disk_count": 1,
            },
            {
                "backup_id": 333333,
                "backup_label": "private-next-label",
                "backup_status": "provider-added-progress-state",
                "backup_kind": "snapshot",
                "snapshot_state": "in_progress",
                "provider_type": "provider-added-snapshot-kind",
                "available": None,
                "created_at": "2026-05-06T14:00:00",
                "finished_at": None,
                "updated_at": "2026-05-06T14:01:00",
                "config_count": 1,
                "disk_count": None,
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
        self.assertEqual(manifest["outcome"]["execution_state"], "completed")
        self.assertEqual(manifest["outcome"]["retry_classification"], "safe_to_rerun_read_only")
        self.assertEqual(manifest["outcome"]["idempotency_boundary"], "read_only_provider_request")
        self.assertIs(manifest["outcome"]["partial_execution"], False)
        self.assertIs(manifest["outcome"]["state_uncertain"], False)
        self.assertIs(manifest["outcome"]["operator_review_required"], False)
        self.assertEqual(manifest["outcome"]["provider_reads"][0]["response_received"], True)
        self.assertNotIn("provider_read_completed", manifest["validation"]["checks"])
        self.assertEqual(manifest["validation"]["status"], "passed_with_uncertain_provider_state")
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
                "retry_recovery": {
                    "command_retry_classification": "safe_to_retry",
                    "provider_state_classification": "state_uncertain",
                    "automatic_retry": "not_performed",
                    "runtime_operator_review_required": False,
                    "runtime_state_uncertain": False,
                    "provider_state_uncertain": True,
                },
            },
        )
        self.assertEqual(manifest["state_assessment"]["status"], "uncertain_provider_state")
        self.assertIs(manifest["state_assessment"]["uncertain_state"], True)
        self.assertEqual(manifest["state_assessment"]["stale_metadata"]["reason"], "snapshot_in_progress_present")
        self.assertIs(manifest["state_assessment"]["refresh_before_mutation"]["required"], True)
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

    def test_inspect_reports_provider_local_snapshot_match_without_exposing_label(self) -> None:
        config = BackupLabConfig(
            schema_version="1",
            target=TargetConfig(linode_id=123, snapshot_label="private-target-label"),
        )

        manifest = create_inspect_manifest(config, client=CurrentSnapshotClient("private-target-label"))
        manifest_json = json.dumps(manifest, sort_keys=True)

        self.assertEqual(manifest["validation"]["status"], "passed")
        self.assertEqual(manifest["state_assessment"]["status"], "provider_local_match")
        self.assertEqual(manifest["state_assessment"]["provider_local_match"], "matched")
        self.assertIs(manifest["state_assessment"]["configured_snapshot_label_matches_current"], True)
        self.assertIs(manifest["state_assessment"]["stale_metadata"]["detected"], False)
        self.assertEqual(manifest["review"]["retry_recovery"]["command_retry_classification"], "safe_to_retry")
        self.assertEqual(manifest["review"]["retry_recovery"]["provider_state_classification"], "safe_to_retry")
        self.assertNotIn("private-target-label", manifest_json)

    def test_inspect_reports_provider_local_snapshot_mismatch_as_stale_metadata(self) -> None:
        config = BackupLabConfig(
            schema_version="1",
            target=TargetConfig(linode_id=123, snapshot_label="private-target-label"),
        )

        manifest = create_inspect_manifest(config, client=CurrentSnapshotClient("different-provider-label"))
        manifest_json = json.dumps(manifest, sort_keys=True)

        self.assertEqual(manifest["validation"]["status"], "passed_with_drift_advisory")
        self.assertEqual(manifest["state_assessment"]["status"], "provider_local_mismatch")
        self.assertEqual(manifest["state_assessment"]["provider_local_match"], "mismatched")
        self.assertIs(manifest["state_assessment"]["configured_snapshot_label_matches_current"], False)
        self.assertIs(manifest["state_assessment"]["stale_metadata"]["detected"], True)
        self.assertEqual(
            manifest["state_assessment"]["stale_metadata"]["reason"],
            "current_snapshot_label_differs_from_config",
        )
        self.assertEqual(manifest["review"]["retry_recovery"]["command_retry_classification"], "safe_to_retry")
        self.assertEqual(
            manifest["review"]["retry_recovery"]["provider_state_classification"],
            "operator_review_required",
        )
        self.assertNotIn("private-target-label", manifest_json)
        self.assertNotIn("different-provider-label", manifest_json)

    def test_inspect_treats_current_snapshot_match_with_in_progress_as_uncertain(self) -> None:
        config = BackupLabConfig(
            schema_version="1",
            target=TargetConfig(linode_id=123, snapshot_label="private-target-label"),
        )

        manifest = create_inspect_manifest(config, client=AmbiguousSnapshotClient())
        manifest_json = json.dumps(manifest, sort_keys=True)

        self.assertEqual(manifest["validation"]["status"], "passed_with_uncertain_provider_state")
        self.assertEqual(manifest["state_assessment"]["status"], "uncertain_provider_state")
        self.assertEqual(manifest["state_assessment"]["provider_local_match"], "unknown")
        self.assertIs(manifest["state_assessment"]["configured_snapshot_label_matches_current"], None)
        self.assertEqual(manifest["state_assessment"]["stale_metadata"]["reason"], "snapshot_in_progress_present")
        self.assertIs(manifest["inspection_summary"]["snapshot_current_present"], True)
        self.assertIs(manifest["inspection_summary"]["snapshot_in_progress_present"], True)
        self.assertEqual(
            manifest["inspection_summary"]["status_counts"],
            {"provider-added-progress-state": 1, "successful": 1},
        )
        self.assertEqual(
            manifest["review"]["state_visibility"]["unknown_fields"],
            {
                "available": 1,
                "backup_kind": 0,
                "backup_status": 0,
                "config_count": 1,
                "disk_count": 1,
                "provider_type": 0,
                "snapshot_state_for_snapshot": 0,
            },
        )
        self.assertNotIn("222222", manifest_json)
        self.assertNotIn("333333", manifest_json)
        self.assertNotIn("private-target-label", manifest_json)
        self.assertNotIn("private-next-label", manifest_json)
        self.assertNotIn("2026-05-06T14:00:00", manifest_json)


if __name__ == "__main__":
    unittest.main()
