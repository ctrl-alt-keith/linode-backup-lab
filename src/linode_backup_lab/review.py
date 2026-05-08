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


def backup_state_visibility(public_backups: list[JsonMap]) -> JsonMap:
    """Count missing normalized state fields in public-safe backup records."""

    snapshot_backups = [backup for backup in public_backups if backup.get("backup_kind") == "snapshot"]
    return {
        "provider_backup_state": "read",
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


def not_read_state_visibility(*, skipped_states: list[str]) -> JsonMap:
    return {
        "provider_backup_state": "not_read",
        "skipped_states": sorted(skipped_states),
        "unknown_fields": {},
    }


def _missing_count(items: list[JsonMap], key: str) -> int:
    return sum(1 for item in items if item.get(key) is None)


def _string_or_unknown(value: Any) -> str:
    if isinstance(value, str) and value:
        return value
    return "unknown"
