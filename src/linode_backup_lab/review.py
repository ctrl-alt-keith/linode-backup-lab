"""Concise operator-facing review summaries for manifests."""

from __future__ import annotations

from collections import Counter
from typing import Any

JsonMap = dict[str, Any]


def provider_call_review(provider_calls: JsonMap) -> JsonMap:
    """Summarize provider calls without replacing detailed call records."""

    items = [item for item in provider_calls.get("items", []) if isinstance(item, dict)]
    kind_counts = Counter(_string_or_unknown(item.get("kind")) for item in items)
    operations = sorted({_string_or_unknown(item.get("operation")) for item in items})
    return {
        "occurred": bool(provider_calls.get("occurred")),
        "total": len(items),
        "by_kind": dict(sorted(kind_counts.items())),
        "operations": operations,
    }


def mutation_review(
    mutation_intent: JsonMap,
    *,
    provider_mutations: str,
    skipped_reason: str | None,
) -> JsonMap:
    """Expose mutation posture in one compact, review-oriented object."""

    return {
        "planned_operation": mutation_intent.get("planned_operation"),
        "execution_requested": bool(mutation_intent.get("execution_requested")),
        "execution_allowed": bool(mutation_intent.get("execution_allowed")),
        "execution_performed": bool(mutation_intent.get("execution_performed")),
        "provider_mutations": provider_mutations,
        "skipped_reason": skipped_reason,
    }


def backup_state_visibility(public_backups: list[JsonMap], *, provider_backup_state: str = "read") -> JsonMap:
    """Count missing normalized state fields in public-safe backup records."""

    snapshot_backups = [backup for backup in public_backups if backup.get("backup_kind") == "snapshot"]
    return {
        "provider_backup_state": provider_backup_state,
        "skipped_states": ["provider_mutation"],
        "unknown_fields": {
            "available": _missing_count(public_backups, "available"),
            "backup_kind": _missing_count(public_backups, "backup_kind"),
            "backup_status": _missing_count(public_backups, "backup_status"),
            "config_count": _missing_count(public_backups, "config_count"),
            "disk_count": _missing_count(public_backups, "disk_count"),
            "provider_type": _missing_count(public_backups, "provider_type"),
            "snapshot_state_for_snapshot": _missing_count(snapshot_backups, "snapshot_state"),
        },
    }


def retry_recovery_review(outcome: JsonMap, state_assessment: JsonMap) -> JsonMap:
    """Classify retry posture without implying automatic retry behavior."""

    return {
        "command_retry_classification": _command_retry_classification(outcome),
        "provider_state_classification": _provider_state_classification(state_assessment),
        "automatic_retry": "not_performed",
        "runtime_operator_review_required": bool(outcome.get("operator_review_required")),
        "runtime_state_uncertain": bool(outcome.get("state_uncertain")),
        "provider_state_uncertain": bool(state_assessment.get("uncertain_state")),
    }


def not_read_state_visibility(*, skipped_states: list[str]) -> JsonMap:
    return {
        "provider_backup_state": "not_read",
        "skipped_states": sorted(skipped_states),
        "unknown_fields": {},
    }


def _missing_count(items: list[JsonMap], key: str) -> int:
    return sum(1 for item in items if item.get(key) is None)


def _command_retry_classification(outcome: JsonMap) -> str:
    retry_classification = outcome.get("retry_classification")
    if retry_classification in {
        "safe_to_rerun_no_provider_request",
        "safe_to_rerun_read_only",
        "safe_to_rerun_read_only_after_provider_failure",
    }:
        return "safe_to_retry"
    if outcome.get("operator_review_required"):
        return "operator_review_required"
    if outcome.get("state_uncertain"):
        return "state_uncertain"
    return "operator_review_required"


def _provider_state_classification(state_assessment: JsonMap) -> str:
    state_status = state_assessment.get("status")
    if state_status == "provider_local_match":
        return "safe_to_retry"
    if state_status == "unverified_provider_state":
        return "refresh_before_retry"
    if state_status == "fixture_replayed":
        return "refresh_before_retry"
    if state_status == "provider_local_mismatch":
        return "operator_review_required"
    if state_status in {"uncertain_provider_state", "provider_read_failed"}:
        return "state_uncertain"
    return "operator_review_required"


def _string_or_unknown(value: Any) -> str:
    if isinstance(value, str) and value:
        return value
    return "unknown"
