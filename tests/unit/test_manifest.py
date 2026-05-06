import unittest

from linode_backup_lab.manifest import CONFIG_SCHEMA_VERSION, create_manifest


class ManifestTests(unittest.TestCase):
    def test_manifest_exposes_provider_api_version_separately(self) -> None:
        manifest = create_manifest(action="snapshot", provider_api_version="v4beta", run_id="run-1")

        self.assertEqual(manifest["schema_version"], CONFIG_SCHEMA_VERSION)
        self.assertEqual(manifest["provider"], {"name": "linode", "api_version": "v4beta"})


if __name__ == "__main__":
    unittest.main()
