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


if __name__ == "__main__":
    unittest.main()
