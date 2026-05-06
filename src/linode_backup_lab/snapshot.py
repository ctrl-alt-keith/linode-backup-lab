"""Command-level snapshot helpers.

This module intentionally consumes normalized API shapes only. Provider endpoint
paths and raw Linode response structures stay in `linode_api.py`.
"""

from __future__ import annotations

from typing import Protocol

from .linode_api import DEFAULT_PROVIDER_API_VERSION, JsonMap
from .manifest import create_manifest


class SnapshotClient(Protocol):
    provider_api_version: str

    def create_snapshot(self, linode_id: int, snapshot_label: str) -> JsonMap:
        ...


def snapshot_manifest(
    *,
    linode_id: int,
    snapshot_label: str,
    client: SnapshotClient | None = None,
    provider_api_version: str = DEFAULT_PROVIDER_API_VERSION,
    dry_run: bool = True,
) -> JsonMap:
    version = client.provider_api_version if client is not None else provider_api_version
    manifest = create_manifest(action="snapshot", provider_api_version=version, dry_run=dry_run)
    manifest["resources"].append(
        {
            "resource_type": "snapshot_request",
            "linode_id": linode_id,
            "snapshot_label": snapshot_label,
        }
    )

    if dry_run:
        return manifest

    if client is None:
        raise ValueError("execute snapshot manifests require a client")

    backup = client.create_snapshot(linode_id, snapshot_label)
    manifest["status"] = "succeeded"
    manifest["resources"].append({"resource_type": "backup", **backup})
    return manifest
