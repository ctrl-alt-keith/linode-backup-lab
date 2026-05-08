"""Dry-run planning contract for Linode Backup Lab."""

from __future__ import annotations

from typing import Any

from .config import BackupLabConfig
from .linode_api import DEFAULT_PROVIDER_API_VERSION
from .manifest import create_manifest

SNAPSHOT_OPERATION = "snapshot_request"
SNAPSHOT_REPLACEMENT_SIDE_EFFECT = "replaces_existing_manual_snapshot_for_linode"


def redacted_target_metadata() -> dict[str, Any]:
    """Return public-safe target metadata for plan manifests."""

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


def mutation_intent(*, planned_operation: str | None, reason: str) -> dict[str, Any]:
    return {
        "planned_operation": planned_operation,
        "execution_requested": False,
        "execution_allowed": False,
        "execution_performed": False,
        "reason": reason,
    }


def no_runtime_outcome() -> dict[str, Any]:
    return {
        "status": "not_executed",
        "provider_reads": [],
        "provider_mutations": [],
    }


def unverified_provider_state_assessment() -> dict[str, Any]:
    return {
        "status": "unverified_provider_state",
        "source": "local_config_only",
        "provider_read_performed": False,
        "provider_local_match": "not_checked",
        "stale_metadata": {
            "detected": False,
            "possible": True,
            "reason": "dry-run planning does not read provider backup state",
        },
        "uncertain_state": True,
        "refresh_before_mutation": {
            "required": True,
            "command": "inspect",
            "reason": "read current provider backup state before any future mutation path is allowed",
        },
    }


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
                "provider_calls": no_provider_calls(),
            },
            "config": {
                "schema_version": config.schema_version,
            },
            "planned_actions": [
                {
                    "action": "snapshot_request",
                    "effect": "dry_run_only",
                    "resource_type": "linode_instance",
                    "target": redacted_target_metadata(),
                    "provider_read": False,
                    "provider_mutation": False,
                    "provider_documented_side_effects": [SNAPSHOT_REPLACEMENT_SIDE_EFFECT],
                }
            ],
            "mutation_intent": mutation_intent(
                planned_operation=SNAPSHOT_OPERATION,
                reason="dry-run planning only",
            ),
            "state_assessment": unverified_provider_state_assessment(),
            "outcome": no_runtime_outcome(),
            "validation": {
                "status": "passed_with_unverified_provider_state",
                "checks": [
                    "explicit_config_path",
                    "config_schema_version_supported",
                    "target_linode_id_valid",
                    "target_snapshot_label_valid",
                    "provider_state_not_checked",
                    "refresh_required_before_mutation",
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
            "target": redacted_target_metadata(),
        }
    )
    return manifest
