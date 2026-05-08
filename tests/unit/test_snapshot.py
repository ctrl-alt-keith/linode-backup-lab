import json
import unittest

from linode_backup_lab.config import BackupLabConfig, TargetConfig
from linode_backup_lab.snapshot import snapshot_manifest


class SnapshotTests(unittest.TestCase):
    def test_dry_run_manifest_matches_public_safe_plan_posture(self) -> None:
        config = BackupLabConfig(
            schema_version="1",
            target=TargetConfig(linode_id=987654321, snapshot_label="private-label-value"),
        )

        manifest = snapshot_manifest(config=config)
        manifest_json = json.dumps(manifest, sort_keys=True)

        self.assertEqual(manifest["provider"]["api_version"], "v4")
        self.assertEqual(manifest["action"], "snapshot")
        self.assertEqual(manifest["run_id"], "dry-run-snapshot")
        self.assertEqual(manifest["command"]["provider_calls"], {"occurred": False, "items": []})
        self.assertEqual(manifest["safety"]["provider_mutations"], "not_performed")
        self.assertEqual(manifest["mutation_intent"]["execution_requested"], False)
        self.assertEqual(manifest["state_assessment"]["provider_local_match"], "not_checked")
        self.assertIs(manifest["state_assessment"]["refresh_before_mutation"]["required"], True)
        self.assertEqual(manifest["outcome"]["execution_state"], "not_started")
        self.assertEqual(manifest["outcome"]["retry_classification"], "safe_to_rerun_no_provider_request")
        self.assertEqual(manifest["outcome"]["idempotency_boundary"], "no_provider_request_sent")
        self.assertIs(manifest["outcome"]["operator_review_required"], False)
        self.assertEqual(manifest["review"]["retry_recovery"]["command_retry_classification"], "safe_to_retry")
        self.assertEqual(manifest["review"]["retry_recovery"]["provider_state_classification"], "refresh_before_retry")
        self.assertEqual(manifest["planned_actions"][0]["effect"], "dry_run_only")
        self.assertEqual(
            manifest["planned_actions"][0]["provider_documented_side_effects"],
            ["replaces_existing_manual_snapshot_for_linode"],
        )
        self.assertEqual(manifest["planned_actions"][0]["target"], manifest["resources"][0]["target"])
        self.assertNotIn("987654321", manifest_json)
        self.assertNotIn("private-label-value", manifest_json)
        self.assertIn('"redacted": true', manifest_json)

    def test_snapshot_manifest_accepts_explicit_provider_version_without_provider_calls(self) -> None:
        config = BackupLabConfig(
            schema_version="1",
            target=TargetConfig(linode_id=123, snapshot_label="pre-upgrade"),
        )

        manifest = snapshot_manifest(config=config, provider_api_version="v4beta")

        self.assertEqual(manifest["provider"]["api_version"], "v4beta")
        self.assertEqual(manifest["command"]["provider_calls"], {"occurred": False, "items": []})
        self.assertEqual(manifest["safety"]["provider_reads"], "not_performed")
        self.assertEqual(manifest["safety"]["provider_mutations"], "not_performed")

    def test_snapshot_execution_is_not_available(self) -> None:
        config = BackupLabConfig(
            schema_version="1",
            target=TargetConfig(linode_id=123, snapshot_label="pre-upgrade"),
        )
        with self.assertRaises(ValueError):
            snapshot_manifest(config=config, dry_run=False)


if __name__ == "__main__":
    unittest.main()
