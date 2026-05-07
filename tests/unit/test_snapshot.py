import unittest

from linode_backup_lab.snapshot import snapshot_manifest


class FakeSnapshotClient:
    provider_api_version = "v4beta"


class SnapshotTests(unittest.TestCase):
    def test_dry_run_manifest_uses_stable_resource_names(self) -> None:
        manifest = snapshot_manifest(linode_id=123, snapshot_label="pre-upgrade")

        self.assertEqual(manifest["provider"]["api_version"], "v4")
        self.assertEqual(
            manifest["resources"],
            [{"resource_type": "snapshot_request", "linode_id": 123, "snapshot_label": "pre-upgrade"}],
        )

    def test_snapshot_execution_is_not_available(self) -> None:
        client = FakeSnapshotClient()

        with self.assertRaises(ValueError):
            snapshot_manifest(linode_id=123, snapshot_label="pre-upgrade", client=client, dry_run=False)


if __name__ == "__main__":
    unittest.main()
