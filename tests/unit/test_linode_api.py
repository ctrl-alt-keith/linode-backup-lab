from pathlib import Path
import unittest

from linode_backup_lab.linode_api import (
    DEFAULT_PROVIDER_API_VERSION,
    LinodeApiClient,
    ProviderConfig,
    api_path,
    normalize_backup,
    normalize_backup_collection,
)


class LinodeApiTests(unittest.TestCase):
    def test_api_path_defaults_to_v4(self) -> None:
        self.assertEqual(
            api_path("linode", "instances", 123, "backups"),
            "/v4/linode/instances/123/backups",
        )
        self.assertEqual(DEFAULT_PROVIDER_API_VERSION, "v4")

    def test_api_path_accepts_v4beta_at_boundary(self) -> None:
        self.assertEqual(
            api_path("linode", "instances", 123, "backups", api_version="v4beta"),
            "/v4beta/linode/instances/123/backups",
        )

    def test_invalid_api_version_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ProviderConfig(api_version="v3")

    def test_client_generates_backup_paths_from_provider_config(self) -> None:
        seen: list[tuple[str, str, dict[str, object], dict[str, object] | None]] = []

        def transport(
            method: str,
            url: str,
            headers: dict[str, object],
            body: dict[str, object] | None,
        ) -> dict[str, object]:
            seen.append((method, url, headers, body))
            return {
                "id": 987,
                "label": "pre-upgrade",
                "status": "successful",
                "type": "snapshot",
            }

        client = LinodeApiClient(
            token="token",
            config=ProviderConfig(api_version="v4beta", base_url="https://api.linode.com"),
            transport=transport,
        )

        backup = client.create_snapshot(123, "pre-upgrade")

        self.assertEqual(backup["backup_id"], 987)
        self.assertEqual(
            seen,
            [
                (
                    "POST",
                    "https://api.linode.com/v4beta/linode/instances/123/backups",
                    {"Authorization": "Bearer token", "Content-Type": "application/json"},
                    {"label": "pre-upgrade"},
                )
            ],
        )

    def test_raw_provider_version_paths_stay_in_api_boundary(self) -> None:
        src_root = Path(__file__).resolve().parents[2] / "src" / "linode_backup_lab"
        offenders = []
        for path in src_root.glob("*.py"):
            if path.name == "linode_api.py":
                continue
            text = path.read_text(encoding="utf-8")
            if "/v4/" in text or "/v4beta/" in text:
                offenders.append(path.name)

        self.assertEqual(offenders, [])

    def test_client_exposes_no_live_restore_mutation_helper(self) -> None:
        self.assertFalse(hasattr(LinodeApiClient, "restore_backup"))

        src_root = Path(__file__).resolve().parents[2] / "src" / "linode_backup_lab"
        offenders = []
        for path in src_root.glob("*.py"):
            text = path.read_text(encoding="utf-8")
            if '"restore"' in text or "'restore'" in text:
                offenders.append(path.name)

        self.assertEqual(offenders, [])

    def test_normalize_backup_uses_stable_internal_names(self) -> None:
        backup = normalize_backup(
            {
                "id": 987,
                "label": "pre-upgrade",
                "status": "successful",
                "type": "snapshot",
                "available": True,
                "created": "2026-05-06T12:00:00",
                "finished": "2026-05-06T12:05:00",
            }
        )

        self.assertEqual(
            backup,
            {
                "backup_id": 987,
                "snapshot_label": "pre-upgrade",
                "backup_status": "successful",
                "backup_type": "snapshot",
                "available": True,
                "created_at": "2026-05-06T12:00:00",
                "finished_at": "2026-05-06T12:05:00",
            },
        )

    def test_normalize_backup_collection_flattens_provider_groups(self) -> None:
        backups = normalize_backup_collection(
            {
                "automatic": [
                    {"id": 1, "label": "daily", "status": "successful"},
                ],
                "snapshot": {"id": 2, "label": "manual", "status": "successful"},
            }
        )

        self.assertEqual(
            [(backup["backup_id"], backup["backup_type"]) for backup in backups],
            [(1, "automatic"), (2, "snapshot")],
        )


if __name__ == "__main__":
    unittest.main()
