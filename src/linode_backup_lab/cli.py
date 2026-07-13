"""Minimal command line entrypoint for public-safe backup lab commands."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tomllib

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Callable, Mapping, Sequence, TextIO

from .config import ConfigError, create_config_check_manifest, load_config
from .inspect import InspectClient, create_inspect_failure_manifest, create_inspect_manifest, require_linode_token
from .linode_api import DEFAULT_PROVIDER_API_VERSION, LinodeApiClient, ProviderError
from .plan import create_plan_manifest
from .replay import create_replay_inspect_manifest, load_sanitized_inspect_fixture

PACKAGE_NAME = "linode-backup-lab"


def package_version() -> str:
    try:
        return version(PACKAGE_NAME)
    except PackageNotFoundError:
        pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
        pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
        return str(pyproject["project"]["version"])


def add_version_arg(parser: argparse.ArgumentParser, version_text: str) -> None:
    parser.add_argument(
        "--version",
        action="version",
        version=version_text,
        help="Print the installed package version and exit.",
    )


def build_parser() -> argparse.ArgumentParser:
    version_text = package_version()
    parser = argparse.ArgumentParser(prog="linode-backup-lab")
    add_version_arg(parser, version_text)
    subparsers = parser.add_subparsers(dest="command", required=True)

    config_check_parser = subparsers.add_parser(
        "config-check",
        help="validate config without planning or provider access",
    )
    add_version_arg(config_check_parser, version_text)
    config_check_parser.add_argument(
        "--config",
        required=True,
        type=Path,
        help="explicit path to a backup lab TOML config",
    )

    plan_parser = subparsers.add_parser("plan", help="generate a dry-run plan manifest")
    add_version_arg(plan_parser, version_text)
    plan_parser.add_argument("--config", required=True, type=Path, help="explicit path to a backup lab TOML config")

    inspect_parser = subparsers.add_parser("inspect", help="read provider backup state without mutating resources")
    add_version_arg(inspect_parser, version_text)
    inspect_parser.add_argument("--config", required=True, type=Path, help="explicit path to a backup lab TOML config")

    replay_parser = subparsers.add_parser(
        "inspect-replay",
        help="replay inspect-style output from a sanitized fixture without provider access",
    )
    add_version_arg(replay_parser, version_text)
    replay_parser.add_argument("--config", required=True, type=Path, help="explicit path to a backup lab TOML config")
    replay_parser.add_argument("--fixture", required=True, type=Path, help="explicit path to a sanitized backup fixture")

    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    environ: Mapping[str, str] | None = None,
    inspect_client_factory: Callable[[str], InspectClient] | None = None,
) -> int:
    output = stdout if stdout is not None else sys.stdout
    error_output = stderr if stderr is not None else sys.stderr
    parser = build_parser()
    args = parser.parse_args(argv)
    env = environ if environ is not None else os.environ

    try:
        config = load_config(args.config)
        if args.command == "config-check":
            manifest = create_config_check_manifest(config, command=args.command)
        elif args.command == "plan":
            manifest = create_plan_manifest(config, command=args.command)
        elif args.command == "inspect":
            token = require_linode_token(env)
            factory = inspect_client_factory or (lambda linode_token: LinodeApiClient(token=linode_token))
            client: InspectClient | None = None
            try:
                client = factory(token)
                manifest = create_inspect_manifest(config, client=client, command=args.command)
            except ProviderError as exc:
                provider_api_version = getattr(client, "provider_api_version", DEFAULT_PROVIDER_API_VERSION)
                manifest = create_inspect_failure_manifest(
                    config,
                    provider_error=exc,
                    provider_api_version=provider_api_version,
                    command=args.command,
                )
                json.dump(manifest, output, indent=2, sort_keys=True)
                output.write("\n")
                print(f"error: {exc}", file=error_output)
                return 1
        elif args.command == "inspect-replay":
            fixture_backups = load_sanitized_inspect_fixture(args.fixture)
            manifest = create_replay_inspect_manifest(config, fixture_backups=fixture_backups, command=args.command)
        else:
            parser.error(f"unsupported command: {args.command}")
    except ConfigError as exc:
        print(f"error: {exc}", file=error_output)
        return 2
    except ValueError as exc:
        print(f"error: {exc}", file=error_output)
        return 2

    json.dump(manifest, output, indent=2, sort_keys=True)
    output.write("\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
