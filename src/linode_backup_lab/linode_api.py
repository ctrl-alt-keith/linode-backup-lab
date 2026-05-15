"""Linode API boundary helpers.

Provider API versioning, endpoint paths, and raw response normalization live in
this module so command logic can work with stable project concepts.

`LinodeApiClient` is intentionally a read-only inspection client. Future live
mutation work must introduce an explicit mutation-specific provider boundary
instead of adding write helpers to this client.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

DEFAULT_PROVIDER_API_VERSION = "v4"
SUPPORTED_PROVIDER_API_VERSIONS = ("v4", "v4beta")
DEFAULT_BASE_URL = "https://api.linode.com"
PROVIDER_AUTHORIZATION_HEADER = "Authorization"
PROVIDER_BEARER_TOKEN_PREFIX = "Bearer"
DOCUMENTED_BACKUP_FIELDS = (
    "available",
    "configs",
    "created",
    "disks",
    "finished",
    "id",
    "label",
    "status",
    "type",
    "updated",
)

JsonMap = dict[str, Any]
Transport = Callable[[str, str, JsonMap, JsonMap | None], JsonMap]


class ProviderError(RuntimeError):
    """Raised when a provider read fails with public-safe reporting metadata."""

    def __init__(
        self,
        detail: str | None = None,
        *,
        public_message: str = "Linode provider read failed",
        category: str = "provider_error",
        request_sent: bool = False,
        response_received: bool = False,
        status_code: int | None = None,
    ) -> None:
        super().__init__(public_message)
        self.category = category
        self.public_message = public_message
        self.request_sent = request_sent
        self.response_received = response_received
        self.status_code = status_code
        # `detail` is intentionally not stored or emitted; callers may pass
        # raw exception detail without making it part of the public contract.
        _ = detail


class ProviderReadOnlyViolation(ProviderError):
    """Raised if a caller attempts to use the read-only provider client to mutate."""


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
    """Small injectable read-only client for backup-service inspection."""

    token: str
    config: ProviderConfig = ProviderConfig()
    transport: Transport | None = None

    def __post_init__(self) -> None:
        if not self.token.strip():
            raise ValueError("LinodeApiClient requires a non-empty token")
        if self.transport is None:
            self.transport = ReadOnlyHttpTransport()

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

    def request(self, method: str, path: str, body: JsonMap | None = None) -> JsonMap:
        method = method.upper()
        if method != "GET" or body is not None:
            raise ProviderReadOnlyViolation("LinodeApiClient only permits read-only GET requests")
        headers = {
            PROVIDER_AUTHORIZATION_HEADER: f"{PROVIDER_BEARER_TOKEN_PREFIX} {self.token}",
            "Content-Type": "application/json",
        }
        return self.transport(method, self.config.base_url.rstrip("/") + path, headers, body)


@dataclass(frozen=True)
class ReadOnlyHttpTransport:
    """Tiny stdlib transport for live read-only Linode API inspection."""

    timeout_seconds: float = 30.0

    def __call__(self, method: str, url: str, headers: JsonMap, body: JsonMap | None) -> JsonMap:
        if method.upper() != "GET" or body is not None:
            raise ProviderReadOnlyViolation("read-only transport only permits GET requests without a body")

        request = Request(url, headers={str(key): str(value) for key, value in headers.items()}, method="GET")
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = response.read().decode("utf-8")
        except HTTPError as exc:
            raise ProviderError(
                public_message=f"Linode API read failed with HTTP {exc.code}",
                category="http_error",
                request_sent=True,
                response_received=True,
                status_code=exc.code,
            ) from exc
        except URLError as exc:
            raise ProviderError(
                detail=str(exc.reason),
                public_message="Linode API read failed before receiving a response",
                category="network_error",
                request_sent=True,
                response_received=False,
            ) from exc

        try:
            decoded = json.loads(payload) if payload else {}
        except json.JSONDecodeError as exc:
            raise ProviderError(
                detail=str(exc),
                public_message="Linode API returned invalid JSON",
                category="invalid_json",
                request_sent=True,
                response_received=True,
            ) from exc
        if not isinstance(decoded, dict):
            raise ProviderError(
                public_message="Linode API returned an unexpected JSON shape",
                category="unexpected_json_shape",
                request_sent=True,
                response_received=True,
            )
        return decoded


def normalize_backup_collection(raw: JsonMap) -> list[JsonMap]:
    """Normalize the Linode backups collection into stable backup records."""

    backups: list[JsonMap] = []
    automatic = raw.get("automatic")
    if isinstance(automatic, list):
        for item in automatic:
            if isinstance(item, dict):
                backups.append(normalize_backup(item, backup_kind="automatic"))
    snapshot = raw.get("snapshot")
    if isinstance(snapshot, dict):
        current = snapshot.get("current")
        if isinstance(current, dict) and current:
            backups.append(normalize_backup(current, backup_kind="snapshot", snapshot_state="current"))
        in_progress = snapshot.get("in_progress")
        if isinstance(in_progress, dict) and in_progress:
            backups.append(normalize_backup(in_progress, backup_kind="snapshot", snapshot_state="in_progress"))
    return backups


def normalize_backup(raw: JsonMap, *, backup_kind: str | None = None, snapshot_state: str | None = None) -> JsonMap:
    """Normalize one provider backup response into project field names."""

    backup_id = raw.get("id")
    configs = raw.get("configs")
    disks = raw.get("disks")
    return {
        "backup_id": backup_id,
        "backup_label": raw.get("label"),
        "backup_status": raw.get("status"),
        "backup_kind": backup_kind or raw.get("type"),
        "snapshot_state": snapshot_state,
        "provider_type": raw.get("type"),
        "available": raw.get("available"),
        "created_at": raw.get("created"),
        "finished_at": raw.get("finished"),
        "updated_at": raw.get("updated"),
        "config_count": len(configs) if isinstance(configs, list) else None,
        "disk_count": len(disks) if isinstance(disks, list) else None,
    }
