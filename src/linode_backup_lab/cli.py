"""Minimal command line entrypoint for public-safe backup lab commands."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Callable, Mapping, Sequence, TextIO

from .config import ConfigError, load_config
from .inspect import InspectClient, create_inspect_manifest, require_linode_token
from .linode_api import LinodeApiClient, ProviderError
from .plan import create_plan_manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="linode-backup-lab")
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan_parser = subparsers.add_parser("plan", help="generate a dry-run plan manifest")
    plan_parser.add_argument("--config", required=True, type=Path, help="explicit path to a backup lab TOML config")

    inspect_parser = subparsers.add_parser("inspect", help="read provider backup state without mutating resources")
    inspect_parser.add_argument("--config", required=True, type=Path, help="explicit path to a backup lab TOML config")

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
        if args.command == "plan":
            manifest = create_plan_manifest(config, command=args.command)
        elif args.command == "inspect":
            token = require_linode_token(env)
            factory = inspect_client_factory or (lambda linode_token: LinodeApiClient(token=linode_token))
            manifest = create_inspect_manifest(config, client=factory(token), command=args.command)
        else:
            parser.error(f"unsupported command: {args.command}")
    except ConfigError as exc:
        print(f"error: {exc}", file=error_output)
        return 2
    except ValueError as exc:
        print(f"error: {exc}", file=error_output)
        return 2
    except ProviderError as exc:
        print(f"error: {exc}", file=error_output)
        return 1

    json.dump(manifest, output, indent=2, sort_keys=True)
    output.write("\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
