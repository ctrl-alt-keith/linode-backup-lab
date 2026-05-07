"""Command-level snapshot helpers."""

from __future__ import annotations

from .config import BackupLabConfig
from .linode_api import DEFAULT_PROVIDER_API_VERSION, JsonMap
from .plan import create_plan_manifest


def snapshot_manifest(
    *,
    config: BackupLabConfig,
    provider_api_version: str = DEFAULT_PROVIDER_API_VERSION,
    dry_run: bool = True,
) -> JsonMap:
    if not dry_run:
        raise ValueError("snapshot execution is not implemented; dry-run planning only")

    return create_plan_manifest(
        config,
        command="snapshot",
        provider_api_version=provider_api_version,
    )
