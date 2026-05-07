# Linode Backup Lab

Personal, public-safe lab scaffold for backup validation, snapshot validation,
snapshot inspection, and future restore-drill validation on Linode.

This is a personal open-source project. It is not affiliated with, endorsed by,
or supported by Linode, Akamai, or their affiliates. It makes no production
availability, disaster recovery, restore success, data integrity, or operational
safety guarantees.

The project starts intentionally small. Feature work should stay scoped,
safety-oriented, dry-run-first, and validated through `make check`.

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
intent, validation checks, mutation intent, and safety decisions. It does not
read from Linode, mutate Linode resources, require `LINODE_TOKEN`, or perform
cleanup.

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
project shapes such as `linode_id`, `backup_id`, `snapshot_label`,
and `backup_status` instead of raw provider response fields where practical.

Manifests record the provider API version separately from the project
`schema_version` for audit and debugging visibility.

## License

Licensed under the Apache License, Version 2.0. See `LICENSE`.
