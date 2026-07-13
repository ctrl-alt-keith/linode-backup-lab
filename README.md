# Linode Backup Lab

Personal, public-safe lab scaffold for backup validation, snapshot validation,
snapshot inspection, and future restore-drill validation on Linode.

This is a personal open-source project. It is not affiliated with, endorsed by,
or supported by Linode, Akamai, or their affiliates. It makes no production
availability, disaster recovery, restore success, data integrity, or operational
safety guarantees.

The project starts intentionally small. Feature work should stay scoped,
safety-oriented, dry-run-first, and validated through `make check`.

## Installation

Requires Python 3.13 or newer.

Install from a repository checkout for local development:

```sh
git clone https://github.com/ctrl-alt-keith/linode-backup-lab.git
cd linode-backup-lab
python -m pip install -e .
linode-backup-lab --help
linode-backup-lab --version
```

`pipx` can install the command into an isolated environment from the checkout:

```sh
pipx install .
linode-backup-lab --help
linode-backup-lab --version
```

Install directly from the GitHub repository URL:

```sh
pipx install "git+https://github.com/ctrl-alt-keith/linode-backup-lab.git"
linode-backup-lab --help
```

Install the released `v0.1.0` tag explicitly:

```sh
pipx install "git+https://github.com/ctrl-alt-keith/linode-backup-lab.git@v0.1.0"
linode-backup-lab --version
```

Replace `v0.1.0` with a later released tag when one exists. To refresh the same
GitHub install, or to rebuild it with the original install options:

```sh
pipx reinstall linode-backup-lab
```

To move to a specific GitHub ref or tag, force-install that ref:

```sh
pipx install --force "git+https://github.com/ctrl-alt-keith/linode-backup-lab.git@v0.1.0"
```

Uninstall the command with:

```sh
pipx uninstall linode-backup-lab
```

The module entry point remains supported from an installed environment:

```sh
python -m linode_backup_lab --help
python -m linode_backup_lab --version
```

This repository is installable from a checkout, from GitHub refs, and from
built wheel and source distribution artifacts. Release-prep details live in
[`docs/releasing.md`](docs/releasing.md). It does not include PyPI publishing,
automated GitHub release creation, automated tag publishing, provider-live
release checks, restore execution, or snapshot execution.

## Config Check

Validate the explicit config path without generating a snapshot plan, requiring
credentials, or contacting Linode:

```sh
python -m linode_backup_lab config-check --config path/to/backup-lab.toml
```

There is no implicit config discovery. The `--config` path is required. The
command emits a public-safe JSON validation report with redacted target
metadata and `provider_calls.occurred: false`. A valid config-check report only
means local config shape and field checks passed; it is not provider-state
evidence, snapshot readiness, restore authorization, or mutation approval.

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

See [`examples/backup-lab.example.toml`](examples/backup-lab.example.toml) for
a public-safe example file with synthetic placeholders. It is for understanding
the explicit config shape for local dry-run planning and read-only inspection;
it is not production safety guidance, restore authorization, or a credential
storage pattern.

The plan command emits a deterministic JSON manifest that records the command,
dry-run state, config schema version, provider API version, planned snapshot
intent, validation checks, mutation intent, state assessment, and safety
decisions. It redacts raw target values such as `linode_id` and
`snapshot_label`, while preserving presence and validation metadata for review.
It does not read from Linode, mutate Linode resources, require `LINODE_TOKEN`,
or perform cleanup. Because plan is local-only, its state assessment reports
provider state as unverified and advises a fresh inspect before any future
mutation path.

Manifest field semantics, additive-field compatibility guidance,
mutation-intent vocabulary, run identity boundaries, inspect output boundaries,
and CLI exit codes are documented in
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
matches the current manual snapshot slot label without emitting either label. Raw
target values, backup identifiers, labels, provider timestamps, authorization
headers, and raw provider response bodies are not emitted.

Inspect is non-interactive and read-only. Its drift fields compare the
configured label only with the current manual snapshot slot visible in the
backup-service read; they are not general backup health, restore readiness, or
mutation approval. It does not create snapshots, enable or cancel backups,
restore backups, mutate Linode resources, or perform cleanup.
If the provider read fails after local inspect preconditions pass, inspect keeps
the provider-failure exit code `1` and emits a public-safe JSON failure report.
The failure report records only coarse failure metadata; it does not emit token
values, raw provider payloads, provider URLs, authorization headers, target
values, backup identifiers, labels, or timestamps.

## Inspect Replay From Sanitized Fixtures

For documentation, tests, and local UI/debug workflows that must not contact
Linode, replay inspect-style output from an explicit sanitized fixture:

```sh
python -m linode_backup_lab inspect-replay \
  --config examples/backup-lab.example.toml \
  --fixture tests/fixtures/sanitized/inspect-provider-backups.normalized.json
```

Replay is intentionally non-provider and non-credentialed. It requires explicit
`--config` and `--fixture` paths, performs no config discovery, does not require
or read `LINODE_TOKEN`, does not issue provider reads, and does not record either
local path in the manifest. The report marks provider calls and provider reads
as not performed, and it labels state visibility as fixture replay rather than
live provider state.

Fixtures under `tests/fixtures/sanitized/` must contain only public-safe
normalized backup values. Provider identifiers, labels, timestamps, URLs,
headers, raw provider response bodies, and token material must be replaced with
synthetic placeholders such as `SANITIZED_*` or omitted when the field is not
needed. The replay loader rejects obvious raw provider fields and raw-looking
fixture text as a lightweight guardrail; it is not provider validation. Replay
output is useful for checking report shape and inspect UX, but it is not
evidence of live backup-service state or current manual snapshot-slot state and
must not be used as restore approval, drift remediation input, or mutation
preflight.

## Restore Boundary

Restore-drill validation is future conceptual scope only. This repository does
not provide a restore command, restore preflight, restore manifest, restore
provider client, or restore execution path.

The current reports are not enough to authorize a restore. A future restore
design must explicitly model the source Linode, selected provider backup,
restore target, same-region and storage prerequisites, overwrite intent, and
disk UUID collision risk before any live restore mutation is considered. See
[`docs/restore-drill-design.md`](docs/restore-drill-design.md),
[`docs/provider-assumptions.md`](docs/provider-assumptions.md), and
[`docs/manifest-cli-contract.md`](docs/manifest-cli-contract.md) for the current
restore-path boundary.

## Safety Posture

- Dry-run planning and inspection come before any provider mutation.
- Live mutations require explicit future command support and explicit operator
  opt-in.
- CI, Dependabot, branch-protection intent, and required status check names are
  documented in [`docs/governance-ci.md`](docs/governance-ci.md).
- Future live snapshot execution boundary notes are documented in
  [`docs/snapshot-execution-boundary.md`](docs/snapshot-execution-boundary.md).
- Public output should avoid tokens, authorization headers, raw provider
  response bodies, and unnecessary provider-identifying detail.
- Manifests should remain deterministic enough to debug a run while using
  stable project concepts where practical.
- Provider API versions, endpoint paths, and raw response structures stay in the
  API boundary.

## Operator Review Boundaries

Current reports are review artifacts. They can help an operator see what a
command did, what it intentionally skipped, and what provider state was or was
not refreshed. They do not schedule retries, perform recovery, authorize
restore, reconcile provider state, or act as desired-state input.

Retry/recovery review fields keep command retry safety separate from provider
state posture. A command may be safe to rerun while still requiring a fresh
inspect or operator review before any future mutation path.

## Scope

Linode Backup Lab is for narrow validation and restore-readiness workflow
exploration:

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
