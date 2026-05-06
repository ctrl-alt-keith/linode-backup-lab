"""Linode API boundary helpers.

Provider API versioning, endpoint paths, and raw response normalization live in
this module so command logic can work with stable project concepts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import quote

DEFAULT_PROVIDER_API_VERSION = "v4"
SUPPORTED_PROVIDER_API_VERSIONS = ("v4", "v4beta")
DEFAULT_BASE_URL = "https://api.linode.com"

JsonMap = dict[str, Any]
Transport = Callable[[str, str, JsonMap, JsonMap | None], JsonMap]


@dataclass(frozen=True)
class ProviderConfig:
    """Minimal provider configuration kept separate from project config schemas."""

    api_version: str = DEFAULT_PROVIDER_API_VERSION
    base_url: str = DEFAULT_BASE_URL

    def __post_init__(self) -> None:
        validate_provider_api_version(self.api_version)


def validate_provider_api_version(api_version: str) -> str:
    if api_version not in SUPPORTED_PROVIDER_API_VERSIONS:
        supported = ", ".join(SUPPORTED_PROVIDER_API_VERSIONS)
        raise ValueError(f"unsupported Linode provider API version {api_version!r}; expected one of: {supported}")
    return api_version


def api_path(*parts: object, api_version: str = DEFAULT_PROVIDER_API_VERSION) -> str:
    """Build a Linode API path with the provider version as the leading segment."""

    version = validate_provider_api_version(api_version)
    encoded_parts = [quote(str(part).strip("/"), safe="") for part in parts if str(part).strip("/")]
    return "/" + "/".join([version, *encoded_parts])


@dataclass
class LinodeApiClient:
    """Small injectable client for backup-service endpoints."""

    token: str
    config: ProviderConfig = ProviderConfig()
    transport: Transport | None = None

    @property
    def provider_api_version(self) -> str:
        return self.config.api_version

    def path(self, *parts: object) -> str:
        return api_path(*parts, api_version=self.provider_api_version)

    def url(self, *parts: object) -> str:
        return self.config.base_url.rstrip("/") + self.path(*parts)

    def list_backups(self, linode_id: int) -> list[JsonMap]:
        raw = self.request("GET", self.path("linode", "instances", linode_id, "backups"))
        return normalize_backup_collection(raw)

    def get_backup(self, linode_id: int, backup_id: int) -> JsonMap:
        raw = self.request("GET", self.path("linode", "instances", linode_id, "backups", backup_id))
        return normalize_backup(raw)

    def create_snapshot(self, linode_id: int, snapshot_label: str) -> JsonMap:
        raw = self.request(
            "POST",
            self.path("linode", "instances", linode_id, "backups"),
            {"label": snapshot_label},
        )
        return normalize_backup(raw)

    def restore_backup(self, linode_id: int, backup_id: int, restore_target: int, *, overwrite: bool = False) -> JsonMap:
        raw = self.request(
            "POST",
            self.path("linode", "instances", linode_id, "backups", backup_id, "restore"),
            {"linode_id": restore_target, "overwrite": overwrite},
        )
        return normalize_restore_response(raw, restore_target=restore_target)

    def request(self, method: str, path: str, body: JsonMap | None = None) -> JsonMap:
        if self.transport is None:
            raise RuntimeError("LinodeApiClient requires an injected transport before making API requests")
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        return self.transport(method, self.config.base_url.rstrip("/") + path, headers, body)


def normalize_backup_collection(raw: JsonMap) -> list[JsonMap]:
    """Normalize the Linode backups collection into stable backup records."""

    backups: list[JsonMap] = []
    for item in raw.get("automatic", []):
        backups.append(normalize_backup(item, backup_type="automatic"))
    snapshot = raw.get("snapshot")
    if isinstance(snapshot, dict) and snapshot:
        backups.append(normalize_backup(snapshot, backup_type="snapshot"))
    return backups


def normalize_backup(raw: JsonMap, *, backup_type: str | None = None) -> JsonMap:
    """Normalize one provider backup response into project field names."""

    backup_id = raw.get("id")
    return {
        "backup_id": backup_id,
        "snapshot_label": raw.get("label"),
        "backup_status": raw.get("status"),
        "backup_type": backup_type or raw.get("type"),
        "available": raw.get("available"),
        "created_at": raw.get("created"),
        "finished_at": raw.get("finished"),
    }


def normalize_restore_response(raw: JsonMap, *, restore_target: int) -> JsonMap:
    return {
        "restore_target": restore_target,
        "accepted": True,
        "provider_response": raw,
    }
