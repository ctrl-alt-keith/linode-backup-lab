"""Explicit project config loading for dry-run planning."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import tomllib

from .manifest import create_manifest, no_provider_calls, redacted_target_metadata

CONFIG_SCHEMA_VERSION = "1"
SNAPSHOT_LABEL_MIN_LENGTH = 1
SNAPSHOT_LABEL_MAX_LENGTH = 255


class ConfigError(ValueError):
    """Raised when an explicit project config cannot be loaded or validated."""


@dataclass(frozen=True)
class ConfigValidationIssue:
    path: str
    message: str
    hint: str


@dataclass(frozen=True)
class TargetConfig:
    linode_id: int
    snapshot_label: str


@dataclass(frozen=True)
class BackupLabConfig:
    schema_version: str
    target: TargetConfig


def load_config(path: str | Path) -> BackupLabConfig:
    """Load a config from the exact path supplied by the caller."""

    config_path = Path(path)
    try:
        with config_path.open("rb") as config_file:
            raw_config = tomllib.load(config_file)
    except FileNotFoundError as exc:
        raise ConfigError(f"config file not found: {config_path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"invalid TOML config: {exc}") from exc

    return validate_config(raw_config, config_path=config_path)


def create_config_check_manifest(
    config: BackupLabConfig,
    *,
    command: str = "config-check",
    run_id: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Create a public-safe config-only validation report."""

    provider_calls = no_provider_calls()
    manifest = create_manifest(
        action=command,
        dry_run=True,
        run_id=run_id,
        created_at=created_at,
    )
    manifest.update(
        {
            "status": "valid",
            "command": {
                "name": command,
                "config_source": "explicit",
                "config_path_recorded": False,
                "provider_calls": provider_calls,
            },
            "config": {
                "schema_version": config.schema_version,
                "target": redacted_target_metadata(),
            },
            "validation": {
                "status": "passed",
                "checks": [
                    "explicit_config_path",
                    "config_schema_version_supported",
                    "target_linode_id_valid",
                    "target_snapshot_label_valid",
                    "provider_state_not_checked",
                ],
            },
            "safety": {
                "credentials": "not_required",
                "linode_token_required": False,
                "provider_reads": "not_performed",
                "provider_mutations": "not_performed",
                "target_values": "redacted",
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


def validate_config(raw_config: dict[str, Any], *, config_path: str | Path | None = None) -> BackupLabConfig:
    issues: list[ConfigValidationIssue] = []
    allowed_root_keys = {"schema_version", "target"}
    unknown_root_keys = sorted(set(raw_config) - allowed_root_keys)
    if unknown_root_keys:
        issues.append(
            ConfigValidationIssue(
                path="<root>",
                message=f"unsupported config key(s): {', '.join(unknown_root_keys)}",
                hint="Remove unsupported top-level keys; supported keys are schema_version and target.",
            )
        )

    schema_version = raw_config.get("schema_version")
    if schema_version != CONFIG_SCHEMA_VERSION:
        issues.append(
            ConfigValidationIssue(
                path="schema_version",
                message=f"unsupported config schema_version {schema_version!r}; expected {CONFIG_SCHEMA_VERSION!r}",
                hint=f'Set schema_version = "{CONFIG_SCHEMA_VERSION}".',
            )
        )

    raw_target = raw_config.get("target")
    if not isinstance(raw_target, dict):
        issues.append(
            ConfigValidationIssue(
                path="target",
                message="config requires a [target] table",
                hint="Add a [target] table with linode_id and snapshot_label.",
            )
        )
        raise ConfigError(format_config_validation_error(issues, config_path=config_path))

    allowed_target_keys = {"linode_id", "snapshot_label"}
    unknown_target_keys = sorted(set(raw_target) - allowed_target_keys)
    if unknown_target_keys:
        issues.append(
            ConfigValidationIssue(
                path="target",
                message=f"unsupported target key(s): {', '.join(unknown_target_keys)}",
                hint="Remove unsupported [target] keys; supported keys are linode_id and snapshot_label.",
            )
        )

    linode_id = raw_target.get("linode_id")
    if isinstance(linode_id, bool) or not isinstance(linode_id, int) or linode_id <= 0:
        issues.append(
            ConfigValidationIssue(
                path="target.linode_id",
                message="target.linode_id must be a positive integer",
                hint="Set target.linode_id to the numeric Linode instance id, for example 123456.",
            )
        )

    snapshot_label = raw_target.get("snapshot_label")
    if not isinstance(snapshot_label, str):
        issues.append(
            ConfigValidationIssue(
                path="target.snapshot_label",
                message="target.snapshot_label must be a string with length 1..255 after trimming whitespace",
                hint='Set target.snapshot_label to the manual snapshot label, for example "pre-upgrade".',
            )
        )
        snapshot_label = ""
    else:
        snapshot_label = snapshot_label.strip()
        if not SNAPSHOT_LABEL_MIN_LENGTH <= len(snapshot_label) <= SNAPSHOT_LABEL_MAX_LENGTH:
            issues.append(
                ConfigValidationIssue(
                    path="target.snapshot_label",
                    message="target.snapshot_label must be a string with length 1..255 after trimming whitespace",
                    hint="Use a non-empty label no longer than 255 characters after trimming whitespace.",
                )
            )

    if issues:
        raise ConfigError(format_config_validation_error(issues, config_path=config_path))

    return BackupLabConfig(
        schema_version=schema_version,
        target=TargetConfig(linode_id=linode_id, snapshot_label=snapshot_label),
    )


def format_config_validation_error(
    issues: list[ConfigValidationIssue],
    *,
    config_path: str | Path | None = None,
) -> str:
    location = f" {config_path}" if config_path is not None else ""
    issue_label = "issue" if len(issues) == 1 else "issues"
    lines = [f"invalid config{location}: {len(issues)} validation {issue_label}"]
    for issue in issues:
        lines.append(f"- {issue.path}: {issue.message}")
        lines.append(f"  hint: {issue.hint}")
    return "\n".join(lines)
