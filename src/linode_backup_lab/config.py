"""Explicit project config loading for dry-run planning."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:  # pragma: no cover - exercised only on Python 3.10
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised only on Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]

CONFIG_SCHEMA_VERSION = "1"


class ConfigError(ValueError):
    """Raised when an explicit project config cannot be loaded or validated."""


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

    return validate_config(raw_config)


def validate_config(raw_config: dict[str, Any]) -> BackupLabConfig:
    allowed_root_keys = {"schema_version", "target"}
    unknown_root_keys = sorted(set(raw_config) - allowed_root_keys)
    if unknown_root_keys:
        raise ConfigError(f"unsupported config key(s): {', '.join(unknown_root_keys)}")

    schema_version = raw_config.get("schema_version")
    if schema_version != CONFIG_SCHEMA_VERSION:
        raise ConfigError(f"unsupported config schema_version {schema_version!r}; expected {CONFIG_SCHEMA_VERSION!r}")

    raw_target = raw_config.get("target")
    if not isinstance(raw_target, dict):
        raise ConfigError("config requires a [target] table")

    allowed_target_keys = {"linode_id", "snapshot_label"}
    unknown_target_keys = sorted(set(raw_target) - allowed_target_keys)
    if unknown_target_keys:
        raise ConfigError(f"unsupported target key(s): {', '.join(unknown_target_keys)}")

    linode_id = raw_target.get("linode_id")
    if isinstance(linode_id, bool) or not isinstance(linode_id, int) or linode_id <= 0:
        raise ConfigError("target.linode_id must be a positive integer")

    snapshot_label = raw_target.get("snapshot_label")
    if not isinstance(snapshot_label, str) or not snapshot_label.strip():
        raise ConfigError("target.snapshot_label must be a non-empty string")

    return BackupLabConfig(
        schema_version=schema_version,
        target=TargetConfig(linode_id=linode_id, snapshot_label=snapshot_label.strip()),
    )
