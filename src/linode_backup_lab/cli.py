"""Minimal command line entrypoint for dry-run planning."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence, TextIO

from .config import ConfigError, load_config
from .plan import create_plan_manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="linode-backup-lab")
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan_parser = subparsers.add_parser("plan", help="generate a dry-run plan manifest")
    plan_parser.add_argument("--config", required=True, type=Path, help="explicit path to a backup lab TOML config")

    return parser


def main(argv: Sequence[str] | None = None, *, stdout: TextIO | None = None, stderr: TextIO | None = None) -> int:
    output = stdout if stdout is not None else sys.stdout
    error_output = stderr if stderr is not None else sys.stderr
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
        manifest = create_plan_manifest(config, command=args.command)
    except ConfigError as exc:
        print(f"error: {exc}", file=error_output)
        return 2

    json.dump(manifest, output, indent=2, sort_keys=True)
    output.write("\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
