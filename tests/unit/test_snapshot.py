import unittest

from linode_backup_lab.snapshot import snapshot_manifest


class FakeSnapshotClient:
    provider_api_version = "v4beta"

    def create_snapshot(self, linode_id: int, snapshot_label: str) -> dict[str, object]:
        self.seen = {"linode_id": linode_id, "snapshot_label": snapshot_label}
        return {
            "backup_id": 987,
            "snapshot_label": snapshot_label,
            "backup_status": "successful",
            "backup_type": "snapshot",
            "available": True,
            "created_at": "2026-05-06T12:00:00",
            "finished_at": "2026-05-06T12:05:00",
        }


class SnapshotTests(unittest.TestCase):
    def test_dry_run_manifest_uses_stable_resource_names(self) -> None:
        manifest = snapshot_manifest(linode_id=123, snapshot_label="pre-upgrade")

        self.assertEqual(manifest["provider"]["api_version"], "v4")
        self.assertEqual(
            manifest["resources"],
            [{"resource_type": "snapshot_request", "linode_id": 123, "snapshot_label": "pre-upgrade"}],
        )

    def test_execute_manifest_consumes_normalized_backup_shape(self) -> None:
        client = FakeSnapshotClient()

        manifest = snapshot_manifest(linode_id=123, snapshot_label="pre-upgrade", client=client, dry_run=False)

        self.assertEqual(manifest["provider"]["api_version"], "v4beta")
        self.assertEqual(manifest["resources"][1]["backup_id"], 987)
        self.assertEqual(manifest["resources"][1]["backup_status"], "successful")
        self.assertNotIn("id", manifest["resources"][1])
        self.assertNotIn("status", manifest["resources"][1])


if __name__ == "__main__":
    unittest.main()
