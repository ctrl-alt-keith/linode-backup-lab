"""Dry-run planning contract for Linode Backup Lab."""

from __future__ import annotations

from typing import Any

from .config import BackupLabConfig
from .linode_api import DEFAULT_PROVIDER_API_VERSION
from .manifest import create_manifest


def create_plan_manifest(
    config: BackupLabConfig,
    *,
    command: str = "plan",
    provider_api_version: str = DEFAULT_PROVIDER_API_VERSION,
    run_id: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Create a deterministic dry-run manifest from validated config."""

    manifest = create_manifest(
        action=command,
        provider_api_version=provider_api_version,
        dry_run=True,
        run_id=run_id,
        created_at=created_at,
    )
    manifest.update(
        {
            "command": {
                "name": command,
                "config_source": "explicit",
                "provider_calls": "not_performed",
            },
            "config": {
                "schema_version": config.schema_version,
            },
            "planned_actions": [
                {
                    "action": "snapshot_request",
                    "effect": "dry_run_only",
                    "resource_type": "linode_instance",
                    "linode_id": config.target.linode_id,
                    "snapshot_label": config.target.snapshot_label,
                    "provider_read": False,
                    "provider_mutation": False,
                }
            ],
            "mutation_intent": {
                "requested": False,
                "allowed": False,
                "reason": "dry-run planning only",
            },
            "validation": {
                "status": "passed",
                "checks": [
                    "explicit_config_path",
                    "config_schema_version_supported",
                    "target_linode_id_valid",
                    "target_snapshot_label_valid",
                ],
            },
            "safety": {
                "credentials": "environment_only",
                "linode_token_required": False,
                "provider_reads": "not_performed",
                "provider_mutations": "not_performed",
                "cleanup": "not_required",
            },
        }
    )
    manifest["resources"].append(
        {
            "resource_type": "linode_instance",
            "linode_id": config.target.linode_id,
        }
    )
    return manifest
