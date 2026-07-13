"""Read-only inspect command manifest helpers."""

from __future__ import annotations

from collections import Counter
from typing import Any, Mapping, Protocol

from .config import BackupLabConfig
from .linode_api import DEFAULT_PROVIDER_API_VERSION, DOCUMENTED_BACKUP_FIELDS, JsonMap, ProviderError
from .manifest import create_manifest, redacted_target_metadata
from .plan import mutation_intent
from .review import (
    backup_state_visibility,
    mutation_review,
    not_read_state_visibility,
    provider_call_review,
    retry_recovery_review,
)


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
    provider_calls = {
        "occurred": True,
        "items": [provider_call],
    }
    intent = mutation_intent(
        planned_operation=None,
        reason="read-only inspection only",
    )
    outcome = {
        "status": "provider_read_completed",
        "execution_state": "completed",
        "partial_execution": False,
        "state_uncertain": False,
        "operator_review_required": False,
        "retry_classification": "safe_to_rerun_read_only",
        "idempotency_boundary": "read_only_provider_request",
        "retry_boundary": "re-running may observe newer provider state but does not mutate resources",
        "provider_reads": [
            {
                **provider_call,
                "request_sent": True,
                "response_received": True,
            }
        ],
        "provider_mutations": [],
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
                "provider_calls": provider_calls,
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
            "review_summary": inspect_review_summary(
                action=command,
                report_status="inspected",
                summary=summary,
                state_assessment=state_assessment,
                provider_read_status="performed",
            ),
            "normalized_backup_state": public_backups,
            "review": {
                "provider_calls": provider_call_review(provider_calls),
                "mutations": mutation_review(
                    intent,
                    provider_mutations="not_performed",
                    skipped_reason="read_only_inspection",
                ),
                "state_visibility": backup_state_visibility(public_backups),
                "retry_recovery": retry_recovery_review(outcome, state_assessment),
            },
            "mutation_intent": intent,
            "state_assessment": state_assessment,
            "outcome": outcome,
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


def create_inspect_failure_manifest(
    config: BackupLabConfig,
    *,
    provider_error: ProviderError,
    provider_api_version: str = DEFAULT_PROVIDER_API_VERSION,
    command: str = "inspect",
    run_id: str | None = None,
    created_at: str | None = None,
) -> JsonMap:
    """Return a public-safe inspect report for failed provider reads."""

    provider_call = {
        "kind": "read",
        "method": "GET",
        "operation": "list_backups",
    }
    failure = public_safe_provider_failure(provider_error)
    provider_calls = {
        "occurred": failure["request_sent"],
        "items": [provider_call] if failure["request_sent"] else [],
    }
    intent = mutation_intent(
        planned_operation=None,
        reason="read-only inspection only",
    )
    state_assessment = failed_provider_state_assessment(provider_read_attempted=failure["request_sent"])
    outcome = {
        "status": "provider_read_failed",
        "execution_state": "failed",
        "partial_execution": False,
        "state_uncertain": True,
        "operator_review_required": False,
        "retry_classification": "safe_to_rerun_read_only_after_provider_failure",
        "idempotency_boundary": "read_only_provider_request",
        "retry_boundary": "re-running retries a read-only provider request and does not mutate resources",
        "provider_reads": [
            {
                **provider_call,
                "request_sent": failure["request_sent"],
                "response_received": failure["response_received"],
                "failure": failure,
            }
        ],
        "provider_mutations": [],
    }

    manifest = create_manifest(
        action=command,
        provider_api_version=provider_api_version,
        dry_run=False,
        run_id=run_id,
        created_at=created_at,
    )
    manifest.update(
        {
            "status": "provider_read_failed",
            "command": {
                "name": command,
                "config_source": "explicit",
                "config_path_recorded": False,
                "token_source": "environment",
                "provider_calls": provider_calls,
            },
            "config": {
                "schema_version": config.schema_version,
            },
            "provider_read": {
                "status": "failed",
                "operation": "list_backups",
                "method": "GET",
                "target": "configured_linode_backups",
                "raw_response_recorded": False,
                "failure": failure,
            },
            "inspection_summary": {
                "target": redacted_target_metadata(),
                "backup_count": None,
                "automatic_backup_count": None,
                "snapshot_current_present": None,
                "snapshot_in_progress_present": None,
                "available_backup_count": None,
                "status_counts": {},
            },
            "review_summary": inspect_review_summary(
                action=command,
                report_status="provider_read_failed",
                summary=failed_inspect_summary(),
                state_assessment=state_assessment,
                provider_read_status="failed",
                provider_failure=failure,
            ),
            "normalized_backup_state": [],
            "review": {
                "provider_calls": provider_call_review(provider_calls),
                "mutations": mutation_review(
                    intent,
                    provider_mutations="not_performed",
                    skipped_reason="read_only_inspection",
                ),
                "state_visibility": not_read_state_visibility(
                    skipped_states=["provider_backup_state", "provider_mutation"],
                ),
                "retry_recovery": retry_recovery_review(outcome, state_assessment),
            },
            "mutation_intent": intent,
            "state_assessment": state_assessment,
            "outcome": outcome,
            "validation": {
                "status": "provider_read_failed",
                "checks": [
                    "explicit_config_path",
                    "config_schema_version_supported",
                    "target_linode_id_valid",
                    "target_snapshot_label_valid",
                    "linode_token_environment_present",
                    "provider_state_refresh_failed",
                ],
            },
            "safety": {
                "credentials": "environment_only",
                "linode_token_required": True,
                "linode_token_recorded": False,
                "provider_reads": "failed",
                "provider_mutations": "not_performed",
                "read_only_enforced": True,
                "raw_provider_response_recorded": False,
                "target_values": "redacted",
                "backup_identifiers": "not_recorded",
                "provider_url_recorded": False,
                "authorization_header_recorded": False,
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


def public_safe_provider_failure(provider_error: ProviderError) -> JsonMap:
    failure = {
        "category": provider_error.category,
        "message": provider_error.public_message,
        "request_sent": provider_error.request_sent,
        "response_received": provider_error.response_received,
        "status_code": provider_error.status_code,
        "raw_response_recorded": False,
        "raw_payload_recorded": False,
        "url_recorded": False,
        "authorization_header_recorded": False,
    }
    if provider_error.status_code is None:
        failure.pop("status_code")
    return failure


def failed_provider_state_assessment(*, provider_read_attempted: bool = False) -> JsonMap:
    return {
        "status": "provider_read_failed",
        "source": "provider_failure_report",
        "provider_read_performed": False,
        "provider_read_attempted": provider_read_attempted,
        "provider_local_match": "not_checked",
        "snapshot_current_present": None,
        "snapshot_in_progress_present": None,
        "configured_snapshot_label_matches_current": None,
        "stale_metadata": {
            "detected": False,
            "possible": True,
            "reason": "provider_read_failed",
        },
        "uncertain_state": True,
        "refresh_before_mutation": {
            "required": True,
            "command": "inspect",
            "reason": "read current provider backup state before any future mutation path is allowed",
        },
    }


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


def failed_inspect_summary() -> JsonMap:
    return {
        "backup_count": None,
        "automatic_backup_count": None,
        "snapshot_current_present": None,
        "snapshot_in_progress_present": None,
        "available_backup_count": None,
        "status_counts": {},
    }


def inspect_review_summary(
    *,
    action: str,
    report_status: str,
    summary: JsonMap,
    state_assessment: JsonMap,
    provider_read_status: str,
    provider_failure: JsonMap | None = None,
) -> JsonMap:
    """Return a compact, deterministic review aid derived from contract fields."""

    state_status = str(state_assessment["status"])
    backup_count = summary["backup_count"]
    headline = f"{action}: {report_status}; {format_backup_count(backup_count)}; {state_status}"

    attention = inspect_attention_notes(
        provider_read_status=provider_read_status,
        state_assessment=state_assessment,
        provider_failure=provider_failure,
    )
    return {
        "headline": headline,
        "provider_read": provider_read_status,
        "state": {
            "status": state_status,
            "provider_local_match": state_assessment["provider_local_match"],
            "snapshot_current_present": state_assessment["snapshot_current_present"],
            "snapshot_in_progress_present": state_assessment["snapshot_in_progress_present"],
            "refresh_before_mutation_required": state_assessment["refresh_before_mutation"]["required"],
        },
        "backups": {
            "total": backup_count,
            "available": summary["available_backup_count"],
            "automatic": summary["automatic_backup_count"],
            "status_counts": sorted_status_counts(summary["status_counts"]),
        },
        "attention": attention,
    }


def inspect_attention_notes(
    *,
    provider_read_status: str,
    state_assessment: JsonMap,
    provider_failure: JsonMap | None = None,
) -> list[str]:
    notes: list[str] = []

    if provider_read_status == "failed":
        failure = provider_failure or {}
        category = failure.get("category", "provider_error")
        message = failure.get("message", "Provider read failed")
        notes.append(f"Provider read failed ({category}): {message}")
        notes.append("Provider backup state was not read; rerun inspect after the provider issue is resolved.")
    elif state_assessment["status"] == "provider_local_mismatch":
        notes.append("Configured snapshot label did not match the current provider snapshot.")
    elif state_assessment["status"] == "uncertain_provider_state":
        reason = state_assessment["stale_metadata"]["reason"]
        notes.append(f"Provider snapshot comparison is uncertain: {reason}.")
    elif state_assessment["status"] == "fixture_replayed":
        notes.append("Fixture replay is non-live and does not prove current provider state.")

    if state_assessment["refresh_before_mutation"]["required"]:
        notes.append(state_assessment["refresh_before_mutation"]["reason"])

    return notes


def format_backup_count(backup_count: object) -> str:
    if backup_count is None:
        return "backup count unavailable"
    if backup_count == 1:
        return "1 backup"
    return f"{backup_count} backups"


def sorted_status_counts(status_counts: object) -> list[JsonMap]:
    if not isinstance(status_counts, Mapping):
        return []
    return [
        {"status": str(status), "count": count}
        for status, count in sorted(status_counts.items(), key=lambda item: str(item[0]))
    ]


def require_linode_token(environ: Mapping[str, str]) -> str:
    token = environ.get("LINODE_TOKEN", "").strip()
    if not token:
        raise ValueError("LINODE_TOKEN is required for inspect and must be provided in the environment")
    return token
