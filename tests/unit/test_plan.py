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
                "resources": [{"resource_type": "linode_instance", "linode_id": 123}],
                "command": {
                    "name": "plan",
                    "config_source": "explicit",
                    "provider_calls": "not_performed",
                },
                "config": {"schema_version": "1"},
                "planned_actions": [
                    {
                        "action": "snapshot_request",
                        "effect": "dry_run_only",
                        "resource_type": "linode_instance",
                        "linode_id": 123,
                        "snapshot_label": "pre-upgrade",
                        "provider_read": False,
                        "provider_mutation": False,
                    }
                ],
                "mutation_intent": {
                    "requested": False,
                    "allowed": False,
                    "reason": "dry-run planning only",
                },
                "validation": {
                    "status": "passed",
                    "checks": [
                        "explicit_config_path",
                        "config_schema_version_supported",
                        "target_linode_id_valid",
                        "target_snapshot_label_valid",
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


if __name__ == "__main__":
    unittest.main()
