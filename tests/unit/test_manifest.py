import unittest

from linode_backup_lab.config import BackupLabConfig, TargetConfig
from linode_backup_lab.manifest import (
    BASE_MANIFEST_FIELDS,
    DRY_RUN_CREATED_AT,
    MANIFEST_SCHEMA_VERSION,
    create_manifest,
    manifest_additive_fields,
    manifest_required_view,
)
from linode_backup_lab.plan import create_plan_manifest


class ManifestTests(unittest.TestCase):
    def test_manifest_exposes_provider_api_version_separately(self) -> None:
        manifest = create_manifest(action="snapshot", provider_api_version="v4beta", run_id="run-1")

        self.assertEqual(manifest["schema_version"], MANIFEST_SCHEMA_VERSION)
        self.assertEqual(manifest["provider"], {"name": "linode", "api_version": "v4beta"})

    def test_dry_run_manifest_defaults_are_deterministic(self) -> None:
        manifest = create_manifest(action="plan")

        self.assertEqual(manifest["run_id"], "dry-run-plan")
        self.assertEqual(manifest["created_at"], DRY_RUN_CREATED_AT)
        self.assertEqual(manifest["status"], "planned")

    def test_non_dry_run_manifest_shell_does_not_imply_execution(self) -> None:
        manifest = create_manifest(
            action="inspect",
            dry_run=False,
            run_id="inspect-run",
            created_at="2026-05-07T00:00:00+00:00",
        )

        self.assertEqual(manifest["run_id"], "inspect-run")
        self.assertEqual(manifest["created_at"], "2026-05-07T00:00:00+00:00")
        self.assertEqual(manifest["status"], "initialized")

    def test_required_view_tolerates_additive_manifest_fields(self) -> None:
        config = BackupLabConfig(
            schema_version="1",
            target=TargetConfig(linode_id=123, snapshot_label="pre-upgrade"),
        )
        manifest = create_plan_manifest(config)

        view = manifest_required_view(manifest)

        self.assertEqual(list(view), list(BASE_MANIFEST_FIELDS))
        self.assertEqual(view["schema_version"], MANIFEST_SCHEMA_VERSION)
        self.assertEqual(view["action"], "plan")
        self.assertNotIn("review", view)

    def test_additive_fields_can_be_detected_by_strict_consumers(self) -> None:
        config = BackupLabConfig(
            schema_version="1",
            target=TargetConfig(linode_id=123, snapshot_label="pre-upgrade"),
        )
        manifest = create_plan_manifest(config)

        additive_fields = manifest_additive_fields(manifest)

        self.assertIn("mutation_intent", additive_fields)
        self.assertIn("review", additive_fields)
        self.assertNotIn("schema_version", additive_fields)

        manifest["future_report_packet"] = {"status": "additive"}
        self.assertIn("future_report_packet", manifest_additive_fields(manifest))

    def test_required_view_rejects_missing_required_manifest_fields(self) -> None:
        manifest = create_manifest(action="plan")
        del manifest["run_id"]

        with self.assertRaisesRegex(KeyError, "manifest missing required field\\(s\\): run_id"):
            manifest_required_view(manifest)


if __name__ == "__main__":
    unittest.main()
