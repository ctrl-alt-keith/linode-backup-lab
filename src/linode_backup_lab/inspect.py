"""Read-only inspect command manifest helpers."""

from __future__ import annotations

from collections import Counter
from typing import Any, Mapping, Protocol

from .config import BackupLabConfig
from .linode_api import DOCUMENTED_BACKUP_FIELDS, JsonMap
from .manifest import create_manifest
from .plan import mutation_intent, redacted_target_metadata


class InspectClient(Protocol):
    provider_api_version: str

    def list_backups(self, linode_id: int) -> list[JsonMap]:
        """Return normalized backup records for one configured Linode."""


def create_inspect_manifest(
    config: BackupLabConfig,
    *,
    client: InspectClient,
    command: str = "inspect",
    run_id: str | None = None,
    created_at: str | None = None,
) -> JsonMap:
    """Read provider backup state and return a public-safe inspect manifest."""

    backups = client.list_backups(config.target.linode_id)
    public_backups = [public_safe_backup_state(backup) for backup in backups]
    summary = inspect_summary(public_backups)
    state_assessment = provider_local_state_assessment(config, backups)
    provider_call = {
        "kind": "read",
        "method": "GET",
        "operation": "list_backups",
    }

    manifest = create_manifest(
        action=command,
        provider_api_version=client.provider_api_version,
        dry_run=False,
        run_id=run_id,
        created_at=created_at,
    )
    manifest.update(
        {
            "status": "inspected",
            "command": {
                "name": command,
                "config_source": "explicit",
                "config_path_recorded": False,
                "token_source": "environment",
                "provider_calls": {
                    "occurred": True,
                    "items": [provider_call],
                },
            },
            "config": {
                "schema_version": config.schema_version,
            },
            "provider_read": {
                "status": "performed",
                "operation": "list_backups",
                "method": "GET",
                "target": "configured_linode_backups",
                "raw_response_recorded": False,
            },
            "provider_documented_fields": {
                "backup_record": list(DOCUMENTED_BACKUP_FIELDS),
                "collection": ["automatic", "snapshot.current", "snapshot.in_progress"],
            },
            "inspection_summary": {
                "target": redacted_target_metadata(),
                **summary,
            },
            "normalized_backup_state": public_backups,
            "mutation_intent": mutation_intent(
                planned_operation=None,
                reason="read-only inspection only",
            ),
            "state_assessment": state_assessment,
            "outcome": {
                "status": "provider_read_completed",
                "provider_reads": [
                    {
                        **provider_call,
                        "request_sent": True,
                        "response_received": True,
                    }
                ],
                "provider_mutations": [],
            },
            "validation": {
                "status": validation_status_for_state(state_assessment["status"]),
                "checks": [
                    "explicit_config_path",
                    "config_schema_version_supported",
                    "target_linode_id_valid",
                    "target_snapshot_label_valid",
                    "linode_token_environment_present",
                    "provider_state_refreshed",
                    "provider_local_snapshot_match_checked",
                ],
            },
            "safety": {
                "credentials": "environment_only",
                "linode_token_required": True,
                "linode_token_recorded": False,
                "provider_reads": "performed",
                "provider_mutations": "not_performed",
                "read_only_enforced": True,
                "raw_provider_response_recorded": False,
                "target_values": "redacted",
                "backup_identifiers": "redacted",
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


def provider_local_state_assessment(config: BackupLabConfig, backups: list[JsonMap]) -> JsonMap:
    current_snapshots = [
        backup
        for backup in backups
        if backup.get("backup_kind") == "snapshot" and backup.get("snapshot_state") == "current"
    ]
    in_progress_present = any(
        backup.get("backup_kind") == "snapshot" and backup.get("snapshot_state") == "in_progress"
        for backup in backups
    )
    comparable_current_labels = [
        backup.get("backup_label") for backup in current_snapshots if isinstance(backup.get("backup_label"), str)
    ]
    configured_label_matches_current = config.target.snapshot_label in comparable_current_labels

    if in_progress_present:
        status = "uncertain_provider_state"
        provider_local_match = "unknown"
        reason = "snapshot_in_progress_present"
        stale_detected = False
        stale_possible = True
    elif not current_snapshots:
        status = "provider_local_mismatch"
        provider_local_match = "mismatched"
        reason = "current_snapshot_not_present"
        stale_detected = True
        stale_possible = False
    elif configured_label_matches_current:
        status = "provider_local_match"
        provider_local_match = "matched"
        reason = "current_snapshot_label_matches_config"
        stale_detected = False
        stale_possible = False
    elif not comparable_current_labels:
        status = "uncertain_provider_state"
        provider_local_match = "unknown"
        reason = "current_snapshot_label_not_reported"
        stale_detected = False
        stale_possible = True
    else:
        status = "provider_local_mismatch"
        provider_local_match = "mismatched"
        reason = "current_snapshot_label_differs_from_config"
        stale_detected = True
        stale_possible = False

    return {
        "status": status,
        "source": "fresh_provider_read",
        "provider_read_performed": True,
        "provider_local_match": provider_local_match,
        "snapshot_current_present": bool(current_snapshots),
        "snapshot_in_progress_present": in_progress_present,
        "configured_snapshot_label_matches_current": configured_label_matches_current
        if comparable_current_labels and not in_progress_present
        else None,
        "stale_metadata": {
            "detected": stale_detected,
            "possible": stale_possible,
            "reason": reason,
        },
        "uncertain_state": status == "uncertain_provider_state",
        "refresh_before_mutation": {
            "required": True,
            "command": "inspect",
            "reason": "refresh provider backup state immediately before any future mutation path is allowed",
        },
    }


def validation_status_for_state(state_status: object) -> str:
    if state_status == "provider_local_match":
        return "passed"
    if state_status == "provider_local_mismatch":
        return "passed_with_drift_advisory"
    return "passed_with_uncertain_provider_state"


def public_safe_backup_state(backup: JsonMap) -> JsonMap:
    """Redact identifiers while preserving normalized inspect state."""

    return {
        "backup_kind": backup.get("backup_kind"),
        "snapshot_state": backup.get("snapshot_state"),
        "provider_type": backup.get("provider_type"),
        "backup_status": backup.get("backup_status"),
        "available": backup.get("available"),
        "backup_id": redacted_field(backup.get("backup_id"), "provider_backup_id"),
        "backup_label": redacted_field(backup.get("backup_label"), "provider_label"),
        "created_at": redacted_field(backup.get("created_at"), "provider_timestamp"),
        "finished_at": redacted_field(backup.get("finished_at"), "provider_timestamp"),
        "updated_at": redacted_field(backup.get("updated_at"), "provider_timestamp"),
        "config_count": backup.get("config_count"),
        "disk_count": backup.get("disk_count"),
    }


def redacted_field(value: Any, validated_as: str) -> JsonMap:
    present = value is not None
    return {
        "present": present,
        "redacted": present,
        "validated_as": validated_as if present else "not_present",
    }


def inspect_summary(public_backups: list[JsonMap]) -> JsonMap:
    status_counts = Counter(
        backup["backup_status"] for backup in public_backups if backup.get("backup_status") is not None
    )
    return {
        "backup_count": len(public_backups),
        "automatic_backup_count": sum(1 for backup in public_backups if backup.get("backup_kind") == "automatic"),
        "snapshot_current_present": any(
            backup.get("backup_kind") == "snapshot" and backup.get("snapshot_state") == "current"
            for backup in public_backups
        ),
        "snapshot_in_progress_present": any(
            backup.get("backup_kind") == "snapshot" and backup.get("snapshot_state") == "in_progress"
            for backup in public_backups
        ),
        "available_backup_count": sum(1 for backup in public_backups if backup.get("available") is True),
        "status_counts": dict(sorted(status_counts.items())),
    }


def require_linode_token(environ: Mapping[str, str]) -> str:
    token = environ.get("LINODE_TOKEN", "").strip()
    if not token:
        raise ValueError("LINODE_TOKEN is required for inspect and must be provided in the environment")
    return token
