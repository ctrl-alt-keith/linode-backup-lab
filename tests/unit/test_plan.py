import json
import unittest

from linode_backup_lab.config import BackupLabConfig, TargetConfig
from linode_backup_lab.plan import create_plan_manifest


class PlanTests(unittest.TestCase):
    def test_plan_manifest_is_deterministic_and_operational(self) -> None:
        config = BackupLabConfig(
            schema_version="1",
            target=TargetConfig(linode_id=123, snapshot_label="pre-upgrade"),
        )

        manifest = create_plan_manifest(config)

        self.assertEqual(
            manifest,
            {
                "schema_version": "1",
                "provider": {"name": "linode", "api_version": "v4"},
                "run_id": "dry-run-plan",
                "created_at": "not-recorded",
                "action": "plan",
                "dry_run": True,
                "status": "planned",
                "resources": [
                    {
                        "resource_type": "linode_instance",
                        "target": {
                            "linode_id": {
                                "present": True,
                                "redacted": True,
                                "validated_as": "positive_integer",
                            },
                            "snapshot_label": {
                                "present": True,
                                "redacted": True,
                                "validated_as": "linode_snapshot_label_length_1_255",
                            },
                        },
                    }
                ],
                "command": {
                    "name": "plan",
                    "config_source": "explicit",
                    "config_path_recorded": False,
                    "provider_calls": {
                        "occurred": False,
                        "items": [],
                    },
                },
                "config": {"schema_version": "1"},
                "planned_actions": [
                    {
                        "action": "snapshot_request",
                        "effect": "dry_run_only",
                        "resource_type": "linode_instance",
                        "target": {
                            "linode_id": {
                                "present": True,
                                "redacted": True,
                                "validated_as": "positive_integer",
                            },
                            "snapshot_label": {
                                "present": True,
                                "redacted": True,
                                "validated_as": "linode_snapshot_label_length_1_255",
                            },
                        },
                        "provider_read": False,
                        "provider_mutation": False,
                        "provider_documented_side_effects": [
                            "replaces_existing_manual_snapshot_for_linode",
                        ],
                    }
                ],
                "review": {
                    "provider_calls": {
                        "occurred": False,
                        "total": 0,
                        "by_kind": {},
                        "operations": [],
                    },
                    "mutations": {
                        "planned_operation": "snapshot_request",
                        "execution_requested": False,
                        "execution_allowed": False,
                        "execution_performed": False,
                        "provider_mutations": "not_performed",
                        "skipped_reason": "dry_run_only",
                    },
                    "state_visibility": {
                        "provider_backup_state": "not_read",
                        "skipped_states": [
                            "provider_mutation",
                            "provider_read",
                        ],
                        "unknown_fields": {},
                    },
                    "retry_recovery": {
                        "command_retry_classification": "safe_to_retry",
                        "provider_state_classification": "refresh_before_retry",
                        "automatic_retry": "not_performed",
                        "runtime_operator_review_required": False,
                        "runtime_state_uncertain": False,
                        "provider_state_uncertain": True,
                    },
                },
                "mutation_intent": {
                    "planned_operation": "snapshot_request",
                    "execution_requested": False,
                    "execution_allowed": False,
                    "execution_performed": False,
                    "reason": "dry-run planning only",
                },
                "state_assessment": {
                    "status": "unverified_provider_state",
                    "source": "local_config_only",
                    "provider_read_performed": False,
                    "provider_local_match": "not_checked",
                    "stale_metadata": {
                        "detected": False,
                        "possible": True,
                        "reason": "dry-run planning does not read provider backup state",
                    },
                    "uncertain_state": True,
                    "refresh_before_mutation": {
                        "required": True,
                        "command": "inspect",
                        "reason": "read current provider backup state before any future mutation path is allowed",
                    },
                },
                "outcome": {
                    "status": "not_executed",
                    "execution_state": "not_started",
                    "partial_execution": False,
                    "state_uncertain": False,
                    "operator_review_required": False,
                    "retry_classification": "safe_to_rerun_no_provider_request",
                    "idempotency_boundary": "no_provider_request_sent",
                    "retry_boundary": "re-running repeats local validation and manifest generation only",
                    "provider_reads": [],
                    "provider_mutations": [],
                },
                "validation": {
                    "status": "passed_with_unverified_provider_state",
                    "checks": [
                        "explicit_config_path",
                        "config_schema_version_supported",
                        "target_linode_id_valid",
                        "target_snapshot_label_valid",
                        "provider_state_not_checked",
                        "refresh_required_before_mutation",
                    ],
                },
                "safety": {
                    "credentials": "environment_only",
                    "linode_token_required": False,
                    "provider_reads": "not_performed",
                    "provider_mutations": "not_performed",
                    "cleanup": "not_required",
                },
            },
        )

    def test_plan_manifest_separates_config_and_provider_versions(self) -> None:
        config = BackupLabConfig(
            schema_version="1",
            target=TargetConfig(linode_id=123, snapshot_label="pre-upgrade"),
        )

        manifest = create_plan_manifest(config, provider_api_version="v4beta")

        self.assertEqual(manifest["config"]["schema_version"], "1")
        self.assertEqual(manifest["provider"]["api_version"], "v4beta")

    def test_plan_manifest_does_not_emit_raw_target_values(self) -> None:
        config = BackupLabConfig(
            schema_version="1",
            target=TargetConfig(linode_id=987654321, snapshot_label="private-label-value"),
        )

        manifest_json = json.dumps(create_plan_manifest(config), sort_keys=True)

        self.assertNotIn("987654321", manifest_json)
        self.assertNotIn("private-label-value", manifest_json)
        self.assertIn('"redacted": true', manifest_json)

    def test_plan_manifest_reports_unverified_provider_state(self) -> None:
        config = BackupLabConfig(
            schema_version="1",
            target=TargetConfig(linode_id=123, snapshot_label="pre-upgrade"),
        )

        manifest = create_plan_manifest(config)

        self.assertEqual(manifest["state_assessment"]["status"], "unverified_provider_state")
        self.assertIs(manifest["state_assessment"]["stale_metadata"]["possible"], True)
        self.assertIs(manifest["state_assessment"]["refresh_before_mutation"]["required"], True)
        self.assertEqual(manifest["review"]["retry_recovery"]["command_retry_classification"], "safe_to_retry")
        self.assertEqual(manifest["review"]["retry_recovery"]["provider_state_classification"], "refresh_before_retry")


if __name__ == "__main__":
    unittest.main()
