"""Command-level snapshot helpers.

This module intentionally consumes normalized API shapes only. Provider endpoint
paths and raw Linode response structures stay in `linode_api.py`.
"""

from __future__ import annotations

from typing import Protocol

from .config import BackupLabConfig
from .linode_api import DEFAULT_PROVIDER_API_VERSION, JsonMap
from .plan import create_plan_manifest


class SnapshotClient(Protocol):
    provider_api_version: str


def snapshot_manifest(
    *,
    config: BackupLabConfig,
    client: SnapshotClient | None = None,
    provider_api_version: str = DEFAULT_PROVIDER_API_VERSION,
    dry_run: bool = True,
) -> JsonMap:
    if not dry_run:
        raise ValueError("snapshot execution is not implemented; dry-run planning only")

    version = client.provider_api_version if client is not None else provider_api_version
    return create_plan_manifest(
        config,
        command="snapshot",
        provider_api_version=version,
    )
