# Provider Assumptions

Checked: 2026-05-06.

Linode Backup Lab currently targets the Linode API `v4` provider surface by
default. Linode's official API reference models backup endpoint URLs with an
`{apiVersion}` path parameter and lists `v4` and `v4beta` as allowed values for
backup operations. Provider API version handling is centralized in
`src/linode_backup_lab/linode_api.py`; future provider/API changes should remain
localized there unless a real command-level contract changes.

Config schema versioning is separate from provider API versioning. Manifests
record both the project schema version and the Linode provider API version so
audit/debug output can explain which API surface generated a result.

The initial project config schema is intentionally small:

```toml
schema_version = "1"

[target]
linode_id = 123456
snapshot_label = "pre-upgrade"
```

Config loading is explicit-only through `--config PATH`. The dry-run plan flow
records provider call and mutation decisions in the manifest, but does not
perform provider reads or mutations.

Documented provider behavior is not the same as a project guarantee. This
bootstrap records provider references for backup and snapshot inspection work;
future restore-drill validation must re-check the relevant official restore
documentation before adding any live restore behavior.

## Official References

- Linode API reference, List backups:
  <https://techdocs.akamai.com/linode-api/reference/get-backups>
- Linode API reference, Get a backup:
  <https://techdocs.akamai.com/linode-api/reference/get-backup>
- Linode API reference, Create a snapshot:
  <https://techdocs.akamai.com/linode-api/reference/post-snapshot>
- Linode API reference, Restore a backup:
  <https://techdocs.akamai.com/linode-api/reference/post-restore-backup>

## Local Boundary

- Raw endpoint paths are built only in the API boundary.
- Raw provider response fields are normalized before command helpers consume
  them.
- Stable internal resource concepts include `linode_id`, `backup_id`,
  `snapshot_label`, `backup_status`, and future `restore_target`.
- No provider abstraction framework, API-version negotiation, restore execution,
  restore automation, or compatibility shim exists in this bootstrap.
- Public-facing manifests should prefer normalized project fields and avoid raw
  provider response bodies.
