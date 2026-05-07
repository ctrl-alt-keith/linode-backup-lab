from pathlib import Path
import unittest

from linode_backup_lab.linode_api import (
    DEFAULT_PROVIDER_API_VERSION,
    LinodeApiClient,
    ProviderConfig,
    ProviderReadOnlyViolation,
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

    def test_client_generates_backup_read_paths_from_provider_config(self) -> None:
        seen: list[tuple[str, str, dict[str, object], dict[str, object] | None]] = []

        def transport(
            method: str,
            url: str,
            headers: dict[str, object],
            body: dict[str, object] | None,
        ) -> dict[str, object]:
            seen.append((method, url, headers, body))
            return {
                "automatic": [
                    {
                        "id": 987,
                        "label": None,
                        "status": "successful",
                        "type": "auto",
                    }
                ],
                "snapshot": {},
            }

        client = LinodeApiClient(
            token="token",
            config=ProviderConfig(api_version="v4beta", base_url="https://api.linode.com"),
            transport=transport,
        )

        backups = client.list_backups(123)

        self.assertEqual(backups[0]["backup_id"], 987)
        self.assertEqual(
            seen,
            [
                (
                    "GET",
                    "https://api.linode.com/v4beta/linode/instances/123/backups",
                    {"Authorization": "Bearer token", "Content-Type": "application/json"},
                    None,
                )
            ],
        )

    def test_client_rejects_non_get_methods_before_transport(self) -> None:
        seen: list[str] = []

        def transport(
            method: str,
            url: str,
            headers: dict[str, object],
            body: dict[str, object] | None,
        ) -> dict[str, object]:
            seen.append(method)
            return {}

        client = LinodeApiClient(token="token", transport=transport)

        with self.assertRaises(ProviderReadOnlyViolation):
            client.request("POST", client.path("linode", "instances", 123, "backups"), {"label": "pre-upgrade"})

        self.assertEqual(seen, [])

    def test_client_rejects_request_bodies_before_transport(self) -> None:
        seen: list[str] = []

        def transport(
            method: str,
            url: str,
            headers: dict[str, object],
            body: dict[str, object] | None,
        ) -> dict[str, object]:
            seen.append(method)
            return {}

        client = LinodeApiClient(token="token", transport=transport)

        with self.assertRaises(ProviderReadOnlyViolation):
            client.request("GET", client.path("linode", "instances", 123, "backups"), {"unexpected": True})

        self.assertEqual(seen, [])

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

    def test_client_exposes_no_live_mutation_helper(self) -> None:
        self.assertFalse(hasattr(LinodeApiClient, "create_snapshot"))
        self.assertFalse(hasattr(LinodeApiClient, "restore_backup"))

        src_root = Path(__file__).resolve().parents[2] / "src" / "linode_backup_lab"
        offenders = []
        for path in src_root.glob("*.py"):
            text = path.read_text(encoding="utf-8")
            if 'request("POST"' in text or "request('POST'" in text:
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
                "backup_label": "pre-upgrade",
                "backup_status": "successful",
                "backup_kind": "snapshot",
                "snapshot_state": None,
                "provider_type": "snapshot",
                "available": True,
                "created_at": "2026-05-06T12:00:00",
                "finished_at": "2026-05-06T12:05:00",
                "updated_at": None,
                "config_count": None,
                "disk_count": None,
            },
        )

    def test_normalize_backup_collection_flattens_provider_groups_and_snapshot_states(self) -> None:
        backups = normalize_backup_collection(
            {
                "automatic": [
                    {"id": 1, "label": "daily", "status": "successful", "type": "auto"},
                ],
                "snapshot": {
                    "current": {"id": 2, "label": "manual", "status": "successful", "type": "snapshot"},
                    "in_progress": {"id": 3, "label": "manual-next", "status": "running", "type": "snapshot"},
                },
            }
        )

        self.assertEqual(
            [(backup["backup_id"], backup["backup_kind"], backup["snapshot_state"]) for backup in backups],
            [(1, "automatic", None), (2, "snapshot", "current"), (3, "snapshot", "in_progress")],
        )


if __name__ == "__main__":
    unittest.main()
