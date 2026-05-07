import unittest

from linode_backup_lab.manifest import DRY_RUN_CREATED_AT, MANIFEST_SCHEMA_VERSION, create_manifest


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


if __name__ == "__main__":
    unittest.main()
