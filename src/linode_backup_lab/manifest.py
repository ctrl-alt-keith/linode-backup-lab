"""Manifest helpers for public-safe backup lab output."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .linode_api import DEFAULT_PROVIDER_API_VERSION

MANIFEST_SCHEMA_VERSION = "1"
DRY_RUN_CREATED_AT = "not-recorded"
BASE_MANIFEST_FIELDS = (
    "schema_version",
    "provider",
    "run_id",
    "created_at",
    "action",
    "dry_run",
    "status",
    "resources",
)


def redacted_target_metadata() -> dict[str, Any]:
    """Return public-safe target metadata for emitted reports."""

    return {
        "linode_id": {
            "present": True,
            "redacted": True,
            "validated_as": "positive_integer",
        },
        "snapshot_label": {
            "present": True,
            "redacted": True,
            "validated_as": "linode_snapshot_label_length_1_255",
        },
    }


def no_provider_calls() -> dict[str, Any]:
    return {
        "occurred": False,
        "items": [],
    }


def manifest_required_view(
    manifest: Mapping[str, Any],
    required_fields: Iterable[str] = BASE_MANIFEST_FIELDS,
) -> dict[str, Any]:
    """Return a strict consumer's required subset while ignoring additions."""

    fields = tuple(required_fields)
    missing_fields = sorted(field for field in fields if field not in manifest)
    if missing_fields:
        missing = ", ".join(missing_fields)
        raise KeyError(f"manifest missing required field(s): {missing}")

    return {field: manifest[field] for field in fields}


def manifest_additive_fields(
    manifest: Mapping[str, Any],
    known_fields: Iterable[str] = BASE_MANIFEST_FIELDS,
) -> list[str]:
    """Return sorted fields outside a consumer's known manifest field set."""

    known = set(known_fields)
    return sorted(field for field in manifest if field not in known)


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
