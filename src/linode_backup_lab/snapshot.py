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


def snapshot_manifest(
    *,
    linode_id: int,
    snapshot_label: str,
    client: SnapshotClient | None = None,
    provider_api_version: str = DEFAULT_PROVIDER_API_VERSION,
    dry_run: bool = True,
) -> JsonMap:
    if not dry_run:
        raise ValueError("snapshot execution is not implemented; dry-run planning only")

    version = client.provider_api_version if client is not None else provider_api_version
    manifest = create_manifest(action="snapshot", provider_api_version=version, dry_run=dry_run)
    manifest["resources"].append(
        {
            "resource_type": "snapshot_request",
            "linode_id": linode_id,
            "snapshot_label": snapshot_label,
        }
    )

    return manifest
