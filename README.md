# Linode Backup Lab

Personal, public-safe lab scaffold for backup validation, snapshot validation,
snapshot inspection, and future restore-drill validation on Linode.

This is a personal open-source project. It is not affiliated with, endorsed by,
or supported by Linode, Akamai, or their affiliates. It makes no production
availability, disaster recovery, restore success, data integrity, or operational
safety guarantees.

The project starts intentionally small. Feature work should stay scoped,
safety-oriented, dry-run-first, and validated through `make check`.

## Install From Checkout

For local development, install the checkout in editable mode:

```sh
python -m pip install -e .
```

That installs the `linode-backup-lab` console script:

```sh
linode-backup-lab plan --config path/to/backup-lab.toml
LINODE_TOKEN=... linode-backup-lab inspect --config path/to/backup-lab.toml
```

The module entry point remains supported:

```sh
python -m linode_backup_lab plan --config path/to/backup-lab.toml
LINODE_TOKEN=... python -m linode_backup_lab inspect --config path/to/backup-lab.toml
```

From a local checkout, `pipx` can also install the command into an isolated
environment:

```sh
pipx install .
```

This repository is installable from a checkout. It does not include PyPI
publishing, release automation, or package publication workflows.

## Dry-Run Plan

The first command contract is explicit dry-run planning:

```sh
python -m linode_backup_lab plan --config path/to/backup-lab.toml
```

There is no implicit config discovery. The `--config` path is required.

Minimal config:

```toml
schema_version = "1"

[target]
linode_id = 123456
snapshot_label = "pre-upgrade"
```

The plan command emits a deterministic JSON manifest that records the command,
dry-run state, config schema version, provider API version, planned snapshot
intent, validation checks, mutation intent, state assessment, and safety
decisions. It redacts raw target values such as `linode_id` and
`snapshot_label`, while preserving presence and validation metadata for review.
It does not read from Linode, mutate Linode resources, require `LINODE_TOKEN`,
or perform cleanup. Because plan is local-only, its state assessment reports
provider state as unverified and advises a fresh inspect before any future
mutation path.

Manifest field semantics, mutation-intent vocabulary, run identity boundaries,
inspect output boundaries, and CLI exit codes are documented in
[`docs/manifest-cli-contract.md`](docs/manifest-cli-contract.md).

## Read-Only Inspect

The first live provider command is explicit read-only inspection:

```sh
LINODE_TOKEN=... python -m linode_backup_lab inspect --config path/to/backup-lab.toml
```

`LINODE_TOKEN` is environment-only and is never read from config or written to
the report. Inspect uses the configured target to read the Linode backups
collection, then emits a public-safe JSON report with command metadata, project
config schema version, provider API version, validation state, provider-read
status, inspection summary, state assessment, safety decisions, and normalized
backup/snapshot state. Inspect reports whether the configured snapshot label
matches the current provider snapshot label without emitting either label. Raw
target values, backup identifiers, labels, provider timestamps, authorization
headers, and raw provider response bodies are not emitted.

Inspect is non-interactive and read-only. It does not create snapshots, enable
or cancel backups, restore backups, mutate Linode resources, or perform cleanup.

## Restore Boundary

Restore-drill validation is future conceptual scope only. This repository does
not provide a restore command, restore preflight, restore manifest, restore
provider client, or restore execution path.

The current reports are not enough to authorize a restore. A future restore
design must explicitly model the source Linode, selected provider backup,
restore target, same-region and storage prerequisites, overwrite intent, and
disk UUID collision risk before any live restore mutation is considered. See
[`docs/provider-assumptions.md`](docs/provider-assumptions.md) and
[`docs/manifest-cli-contract.md`](docs/manifest-cli-contract.md) for the current
restore-path boundary.

## Safety Posture

- Dry-run planning and inspection come before any provider mutation.
- Live mutations require explicit future command support and explicit operator
  opt-in.
- Public output should avoid tokens, authorization headers, raw provider
  response bodies, and unnecessary provider-identifying detail.
- Manifests should remain deterministic enough to debug a run while using
  stable project concepts where practical.
- Provider API versions, endpoint paths, and raw response structures stay in the
  API boundary.

## Scope

Linode Backup Lab is for narrow validation and recovery workflow exploration:

- backup validation
- snapshot validation
- snapshot inspection
- future restore-drill validation

It is not an operations system, fleet tool, or production recovery service.

## Non-Goals

- orchestration systems
- automatic remediation
- scheduling engines
- desired-state management
- multi-cloud or multi-provider abstractions
- HA/DR orchestration
- secret management
- restore automation

## Related Lab

`ctrl-alt-keith/linode-image-lab` is the sibling public-safe lab for image
capture and deploy validation. Linode Backup Lab stays focused on backup
validation, snapshot inspection, and future restore-drill validation.

## Provider API Versioning

The Linode provider API version defaults to `v4` and is centralized in
`src/linode_backup_lab/linode_api.py`. Command helpers consume normalized
project shapes such as `linode_id`, `backup_id`, `backup_label`,
`backup_kind`, `snapshot_state`, and `backup_status` instead of raw provider
response fields where practical.

Manifests record the provider API version separately from the project
`schema_version` for audit and debugging visibility.

## License

Licensed under the Apache License, Version 2.0. See `LICENSE`.

> AI-generated. Human-verified. Occasionally argued about.
