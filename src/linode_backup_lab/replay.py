"""Non-live fixture replay helpers for inspect-style manifests."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .config import BackupLabConfig
from .inspect import inspect_summary, public_safe_backup_state
from .linode_api import (
    DEFAULT_PROVIDER_API_VERSION,
    DOCUMENTED_BACKUP_FIELDS,
    JsonMap,
    PROVIDER_AUTHORIZATION_HEADER,
    PROVIDER_BEARER_TOKEN_PREFIX,
)
from .manifest import create_manifest
from .plan import mutation_intent, redacted_target_metadata
from .review import backup_state_visibility, mutation_review, provider_call_review, retry_recovery_review

PUBLIC_SAFE_PLACEHOLDER_PREFIX = "SANITIZED_"
SENSITIVE_NORMALIZED_FIELDS = frozenset(
    {
        "backup_id",
        "backup_label",
        "created_at",
        "finished_at",
        "updated_at",
    }
)
RAW_PROVIDER_FIELDS = frozenset(
    {
        "id",
        "label",
        "created",
        "finished",
        "updated",
        "configs",
        "disks",
    }
)
UNSAFE_FIXTURE_PATTERNS = (
    re.compile(r"https?://", re.IGNORECASE),
    re.compile(rf"\b{re.escape(PROVIDER_AUTHORIZATION_HEADER)}\b", re.IGNORECASE),
    re.compile(rf"\b{re.escape(PROVIDER_BEARER_TOKEN_PREFIX)}\s+", re.IGNORECASE),
    re.compile(r"\bLINODE_TOKEN\b"),
    re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:"),
)


def load_sanitized_inspect_fixture(path: Path) -> list[JsonMap]:
    """Load a sanitized normalized backup fixture for inspect replay."""

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"unable to read inspect replay fixture: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"inspect replay fixture is not valid JSON: {exc.msg}") from exc

    if not isinstance(data, list):
        raise ValueError("inspect replay fixture must be a JSON array of backup records")

    backups: list[JsonMap] = []
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"inspect replay fixture item {index} must be a JSON object")
        backup = dict(item)
        validate_public_safe_fixture_backup(backup, index=index)
        backups.append(backup)

    return backups


def validate_public_safe_fixture_backup(backup: JsonMap, *, index: int) -> None:
    """Reject obvious raw provider material in a replay fixture record."""

    raw_fields = sorted(str(key) for key in backup if key in RAW_PROVIDER_FIELDS)
    if raw_fields:
        joined = ", ".join(raw_fields)
        raise ValueError(f"inspect replay fixture item {index} contains raw provider fields: {joined}")

    for key, value in backup.items():
        if key in SENSITIVE_NORMALIZED_FIELDS:
            validate_sanitized_normalized_field(key, value, index=index)
        validate_no_obviously_unsafe_fixture_value(value, index=index)


def validate_sanitized_normalized_field(key: str, value: object, *, index: int) -> None:
    if value is None:
        return
    if isinstance(value, str) and value.startswith(PUBLIC_SAFE_PLACEHOLDER_PREFIX):
        return
    raise ValueError(
        f"inspect replay fixture item {index} field {key} must use a sanitized placeholder or null"
    )


def validate_no_obviously_unsafe_fixture_value(value: object, *, index: int) -> None:
    if isinstance(value, str):
        if any(pattern.search(value) for pattern in UNSAFE_FIXTURE_PATTERNS):
            raise ValueError(f"inspect replay fixture item {index} contains unsafe raw-looking fixture text")
    elif isinstance(value, dict):
        for nested in value.values():
            validate_no_obviously_unsafe_fixture_value(nested, index=index)
    elif isinstance(value, list):
        for nested in value:
            validate_no_obviously_unsafe_fixture_value(nested, index=index)


def create_replay_inspect_manifest(
    config: BackupLabConfig,
    *,
    fixture_backups: list[JsonMap],
    command: str = "inspect-replay",
    run_id: str | None = None,
    created_at: str | None = None,
) -> JsonMap:
    """Replay inspect-style output from a sanitized fixture without provider access."""

    public_backups = [public_safe_backup_state(backup) for backup in fixture_backups]
    summary = inspect_summary(public_backups)
    state_assessment = replay_state_assessment(config, fixture_backups)
    provider_calls = {
        "occurred": False,
        "items": [],
    }
    intent = mutation_intent(
        planned_operation=None,
        reason="fixture replay only",
    )
    outcome = {
        "status": "fixture_replay_completed",
        "execution_state": "completed",
        "partial_execution": False,
        "state_uncertain": False,
        "operator_review_required": False,
        "retry_classification": "safe_to_rerun_no_provider_request",
        "idempotency_boundary": "local_fixture_read",
        "retry_boundary": "re-running reads the same local fixture and does not contact the provider",
        "provider_reads": [],
        "provider_mutations": [],
    }

    manifest = create_manifest(
        action=command,
        provider_api_version=DEFAULT_PROVIDER_API_VERSION,
        dry_run=True,
        run_id=run_id,
        created_at=created_at,
    )
    manifest.update(
        {
            "status": "replayed",
            "command": {
                "name": command,
                "config_source": "explicit",
                "config_path_recorded": False,
                "fixture_source": "explicit",
                "fixture_path_recorded": False,
                "token_source": "not_required",
                "provider_calls": provider_calls,
            },
            "config": {
                "schema_version": config.schema_version,
            },
            "provider_read": {
                "status": "not_performed",
                "operation": None,
                "method": None,
                "target": "configured_linode_backups",
                "raw_response_recorded": False,
                "replay_source": "sanitized_fixture",
            },
            "provider_documented_fields": {
                "backup_record": list(DOCUMENTED_BACKUP_FIELDS),
                "collection": ["automatic", "snapshot.current", "snapshot.in_progress"],
            },
            "fixture_replay": {
                "enabled": True,
                "source": "sanitized_fixture",
                "fixture_path_recorded": False,
                "provider_credentials_required": False,
                "live_provider_state_read": False,
                "provider_currentness_asserted": False,
            },
            "inspection_summary": {
                "target": redacted_target_metadata(),
                **summary,
            },
            "normalized_backup_state": public_backups,
            "review": {
                "provider_calls": provider_call_review(provider_calls),
                "mutations": mutation_review(
                    intent,
                    provider_mutations="not_performed",
                    skipped_reason="fixture_replay_only",
                ),
                "state_visibility": backup_state_visibility(public_backups, provider_backup_state="fixture_replay"),
                "retry_recovery": retry_recovery_review(outcome, state_assessment),
            },
            "mutation_intent": intent,
            "state_assessment": state_assessment,
            "outcome": outcome,
            "validation": {
                "status": "passed_with_fixture_replay",
                "checks": [
                    "explicit_config_path",
                    "explicit_fixture_path",
                    "config_schema_version_supported",
                    "target_linode_id_valid",
                    "target_snapshot_label_valid",
                    "fixture_json_array_loaded",
                    "provider_credentials_not_required",
                    "provider_state_not_read",
                ],
            },
            "safety": {
                "credentials": "not_required",
                "linode_token_required": False,
                "linode_token_recorded": False,
                "provider_reads": "not_performed",
                "provider_mutations": "not_performed",
                "read_only_enforced": True,
                "raw_provider_response_recorded": False,
                "target_values": "redacted",
                "backup_identifiers": "redacted",
                "fixture_replay_only": True,
                "provider_currentness_asserted": False,
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


def replay_state_assessment(config: BackupLabConfig, backups: list[JsonMap]) -> JsonMap:
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
    fixture_label_matches_config = config.target.snapshot_label in comparable_current_labels

    return {
        "status": "fixture_replayed",
        "source": "sanitized_fixture_replay",
        "provider_read_performed": False,
        "provider_local_match": "not_evaluated_live",
        "fixture_local_match": fixture_label_matches_config if comparable_current_labels and not in_progress_present else None,
        "snapshot_current_present": bool(current_snapshots),
        "snapshot_in_progress_present": in_progress_present,
        "configured_snapshot_label_matches_current": None,
        "stale_metadata": {
            "detected": False,
            "possible": True,
            "reason": "fixture_replay_not_live_provider_state",
        },
        "uncertain_state": False,
        "refresh_before_mutation": {
            "required": True,
            "command": "inspect",
            "reason": "fixture replay is non-live and cannot prove current provider state",
        },
    }
