"""Manifest helpers for public-safe backup lab output."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .linode_api import DEFAULT_PROVIDER_API_VERSION

MANIFEST_SCHEMA_VERSION = "1"
DRY_RUN_CREATED_AT = "not-recorded"


def create_manifest(
    *,
    action: str,
    provider_api_version: str = DEFAULT_PROVIDER_API_VERSION,
    dry_run: bool = True,
    run_id: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Create the shared manifest shell used by command-level helpers.

    Non-dry-run callers must set a command-specific final status before
    emitting the manifest. The shared shell records only initialization.
    """

    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "provider": {
            "name": "linode",
            "api_version": provider_api_version,
        },
        "run_id": run_id or (f"dry-run-{action}" if dry_run else f"backup-lab-{uuid4().hex[:12]}"),
        "created_at": created_at or (DRY_RUN_CREATED_AT if dry_run else datetime.now(timezone.utc).isoformat()),
        "action": action,
        "dry_run": dry_run,
        "status": "planned" if dry_run else "initialized",
        "resources": [],
    }
