from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from linode_backup_lab.linode_api import (
    DEFAULT_PROVIDER_API_VERSION,
    LinodeApiClient,
    ProviderError,
    ProviderConfig,
    ProviderReadOnlyViolation,
    ReadOnlyHttpTransport,
    api_path,
    normalize_backup,
    normalize_backup_collection,
)


class FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None

    def read(self) -> bytes:
        return self.payload


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

    def test_get_backup_generates_read_only_backup_detail_path(self) -> None:
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

        client = LinodeApiClient(token="token", transport=transport)

        backup = client.get_backup(123, 987)

        self.assertEqual(backup["backup_id"], 987)
        self.assertEqual(
            seen,
            [
                (
                    "GET",
                    "https://api.linode.com/v4/linode/instances/123/backups/987",
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

    def test_http_transport_rejects_non_get_methods_before_request(self) -> None:
        with patch("linode_backup_lab.linode_api.urlopen") as request:
            with self.assertRaises(ProviderReadOnlyViolation):
                ReadOnlyHttpTransport()(
                    "POST",
                    "https://api.linode.com/v4/linode/instances/112233/backups",
                    {"Authorization": "Bearer token-value"},
                    None,
                )

        request.assert_not_called()

    def test_http_transport_rejects_request_bodies_before_request(self) -> None:
        with patch("linode_backup_lab.linode_api.urlopen") as request:
            with self.assertRaises(ProviderReadOnlyViolation):
                ReadOnlyHttpTransport()(
                    "GET",
                    "https://api.linode.com/v4/linode/instances/112233/backups",
                    {"Authorization": "Bearer token-value"},
                    {"unexpected": True},
                )

        request.assert_not_called()

    def test_provider_error_defaults_do_not_claim_request_attempt(self) -> None:
        error = ProviderError("private setup detail")

        self.assertEqual(str(error), "Linode provider read failed")
        self.assertEqual(error.category, "provider_error")
        self.assertIs(error.request_sent, False)
        self.assertIs(error.response_received, False)
        self.assertIs(error.status_code, None)
        self.assertNotIn("private setup detail", str(error))

    def test_http_transport_reports_http_failure_without_raw_url_or_payload(self) -> None:
        def failing_urlopen(request: object, timeout: float) -> object:
            raise HTTPError(
                url="https://api.linode.com/v4/linode/instances/112233/backups?token=secret",
                code=503,
                msg="provider failure with private detail",
                hdrs=None,
                fp=None,
            )

        with patch("linode_backup_lab.linode_api.urlopen", failing_urlopen):
            with self.assertRaises(ProviderError) as raised:
                ReadOnlyHttpTransport()(
                    "GET",
                    "https://api.linode.com/v4/linode/instances/112233/backups",
                    {"Authorization": "Bearer token-value"},
                    None,
                )

        error = raised.exception
        self.assertEqual(str(error), "Linode API read failed with HTTP 503")
        self.assertEqual(error.category, "http_error")
        self.assertIs(error.request_sent, True)
        self.assertIs(error.response_received, True)
        self.assertEqual(error.status_code, 503)
        self.assertNotIn("112233", str(error))
        self.assertNotIn("token-value", str(error))
        self.assertNotIn("secret", str(error))

    def test_http_transport_reports_network_failure_without_raw_reason(self) -> None:
        def failing_urlopen(request: object, timeout: float) -> object:
            raise URLError("private-network-detail token-value")

        with patch("linode_backup_lab.linode_api.urlopen", failing_urlopen):
            with self.assertRaises(ProviderError) as raised:
                ReadOnlyHttpTransport()(
                    "GET",
                    "https://api.linode.com/v4/linode/instances/112233/backups",
                    {"Authorization": "Bearer token-value"},
                    None,
                )

        error = raised.exception
        self.assertEqual(str(error), "Linode API read failed before receiving a response")
        self.assertEqual(error.category, "network_error")
        self.assertIs(error.request_sent, True)
        self.assertIs(error.response_received, False)
        self.assertIs(error.status_code, None)
        self.assertNotIn("private-network-detail", str(error))
        self.assertNotIn("token-value", str(error))

    def test_http_transport_reports_invalid_json_without_raw_payload(self) -> None:
        with patch("linode_backup_lab.linode_api.urlopen", return_value=FakeResponse(b'{"token": "secret"')):
            with self.assertRaises(ProviderError) as raised:
                ReadOnlyHttpTransport()(
                    "GET",
                    "https://api.linode.com/v4/linode/instances/112233/backups",
                    {"Authorization": "Bearer token-value"},
                    None,
                )

        error = raised.exception
        self.assertEqual(str(error), "Linode API returned invalid JSON")
        self.assertEqual(error.category, "invalid_json")
        self.assertIs(error.request_sent, True)
        self.assertIs(error.response_received, True)
        self.assertNotIn("secret", str(error))
        self.assertNotIn("token-value", str(error))

    def test_http_transport_reports_unexpected_json_shape_without_raw_payload(self) -> None:
        with patch("linode_backup_lab.linode_api.urlopen", return_value=FakeResponse(b'["private-target"]')):
            with self.assertRaises(ProviderError) as raised:
                ReadOnlyHttpTransport()(
                    "GET",
                    "https://api.linode.com/v4/linode/instances/112233/backups",
                    {"Authorization": "Bearer token-value"},
                    None,
                )

        error = raised.exception
        self.assertEqual(str(error), "Linode API returned an unexpected JSON shape")
        self.assertEqual(error.category, "unexpected_json_shape")
        self.assertIs(error.request_sent, True)
        self.assertIs(error.response_received, True)
        self.assertNotIn("private-target", str(error))
        self.assertNotIn("token-value", str(error))

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

    def test_normalize_backup_preserves_unknown_provider_values_without_raw_shape(self) -> None:
        backup = normalize_backup(
            {
                "id": 654,
                "status": "provider-added-state",
                "type": "provider-added-kind",
                "available": True,
                "configs": [{"label": "boot"}, "legacy-config-name"],
                "disks": [{"label": "root"}, {"size": 512}],
            }
        )

        self.assertEqual(
            backup,
            {
                "backup_id": 654,
                "backup_label": None,
                "backup_status": "provider-added-state",
                "backup_kind": "provider-added-kind",
                "snapshot_state": None,
                "provider_type": "provider-added-kind",
                "available": True,
                "created_at": None,
                "finished_at": None,
                "updated_at": None,
                "config_count": 2,
                "disk_count": 2,
            },
        )
        self.assertNotIn("status", backup)
        self.assertNotIn("type", backup)
        self.assertNotIn("configs", backup)
        self.assertNotIn("disks", backup)

    def test_normalize_backup_handles_missing_and_partial_nested_fields(self) -> None:
        backup = normalize_backup(
            {
                "id": 655,
                "status": "successful",
                "configs": None,
                "disks": [{"label": "root"}],
            }
        )

        self.assertEqual(backup["backup_label"], None)
        self.assertEqual(backup["backup_kind"], None)
        self.assertEqual(backup["provider_type"], None)
        self.assertEqual(backup["config_count"], None)
        self.assertEqual(backup["disk_count"], 1)

    def test_normalize_backup_degrades_nested_scalar_fields_to_unknown(self) -> None:
        backup = normalize_backup(
            {
                "id": {"value": 656},
                "label": ["private-label"],
                "status": {"state": "successful"},
                "type": ["snapshot"],
                "available": "true",
                "created": {"timestamp": "2026-05-06T12:00:00"},
                "finished": ["2026-05-06T12:05:00"],
                "updated": 12345,
                "configs": {"items": []},
                "disks": None,
            }
        )

        self.assertEqual(
            backup,
            {
                "backup_id": None,
                "backup_label": None,
                "backup_status": None,
                "backup_kind": None,
                "snapshot_state": None,
                "provider_type": None,
                "available": None,
                "created_at": None,
                "finished_at": None,
                "updated_at": None,
                "config_count": None,
                "disk_count": None,
            },
        )

    def test_normalize_backup_preserves_malformed_timestamp_strings_without_parsing(self) -> None:
        backup = normalize_backup(
            {
                "id": 657,
                "status": "successful",
                "type": "snapshot",
                "available": False,
                "created": "not-a-provider-timestamp",
            }
        )

        self.assertEqual(backup["created_at"], "not-a-provider-timestamp")
        self.assertEqual(backup["finished_at"], None)
        self.assertEqual(backup["updated_at"], None)

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

    def test_normalize_backup_collection_tolerates_unusable_provider_groups(self) -> None:
        backups = normalize_backup_collection(
            {
                "automatic": None,
                "snapshot": {
                    "current": [],
                    "in_progress": {
                        "id": 4,
                        "label": None,
                        "status": "provider-added-progress-state",
                        "type": "provider-added-snapshot-kind",
                    },
                },
            }
        )

        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0]["backup_id"], 4)
        self.assertEqual(backups[0]["backup_kind"], "snapshot")
        self.assertEqual(backups[0]["snapshot_state"], "in_progress")
        self.assertEqual(backups[0]["backup_status"], "provider-added-progress-state")
        self.assertEqual(backups[0]["provider_type"], "provider-added-snapshot-kind")

    def test_normalize_backup_collection_keeps_partial_snapshot_object_without_nested_noise(self) -> None:
        backups = normalize_backup_collection(
            {
                "automatic": [
                    "not-a-backup",
                    {"id": True, "status": {"state": "successful"}, "type": {"kind": "auto"}},
                ],
                "snapshot": {
                    "current": {
                        "status": "provider-added-state",
                        "type": {"kind": "provider-added-snapshot-kind"},
                        "created": ["bad-timestamp-shape"],
                    },
                    "in_progress": [],
                },
            }
        )

        self.assertEqual(len(backups), 2)
        self.assertEqual(
            backups[0],
            {
                "backup_id": None,
                "backup_label": None,
                "backup_status": None,
                "backup_kind": "automatic",
                "snapshot_state": None,
                "provider_type": None,
                "available": None,
                "created_at": None,
                "finished_at": None,
                "updated_at": None,
                "config_count": None,
                "disk_count": None,
            },
        )
        self.assertEqual(backups[1]["backup_kind"], "snapshot")
        self.assertEqual(backups[1]["snapshot_state"], "current")
        self.assertEqual(backups[1]["backup_status"], "provider-added-state")
        self.assertEqual(backups[1]["provider_type"], None)
        self.assertEqual(backups[1]["created_at"], None)


if __name__ == "__main__":
    unittest.main()
