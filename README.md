# Linode Backup Lab

Personal, public-safe lab scaffold for validating Linode backup and snapshot
workflows.

This repository starts intentionally small. Feature work should stay scoped,
safety-oriented, and validated through `make check`.

## Provider API Versioning

The Linode provider API version defaults to `v4` and is centralized in
`src/linode_backup_lab/linode_api.py`. Command helpers consume normalized
project shapes such as `linode_id`, `backup_id`, `snapshot_label`,
`backup_status`, and `restore_target` instead of raw provider response fields
where practical.

Manifests record the provider API version separately from the project
`schema_version` for audit and debugging visibility.
