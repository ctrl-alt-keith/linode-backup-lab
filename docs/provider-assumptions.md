# Provider Assumptions

Checked: 2026-05-07.

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
perform provider reads or mutations. Public manifests do not echo raw
`linode_id` or `snapshot_label` values; they record concise redacted presence
and validation metadata instead. `snapshot_label` is validated locally as a
trimmed string with length `1..255`, matching the official Create a snapshot
request body constraint for `label`.

The inspect flow uses only the documented List backups `GET` operation for the
configured Linode target. The provider boundary normalizes documented backup
record fields such as `id`, `label`, `status`, `type`, `available`, `created`,
`finished`, `updated`, `configs`, and `disks` into project concepts such as
`backup_id`, `backup_label`, `backup_status`, `backup_kind`, `snapshot_state`,
availability, timestamp fields, and config/disk counts. Public inspect reports
redact target values, backup identifiers, backup labels, and provider
timestamps; they keep summary counts, statuses, availability, and normalized
backup/snapshot categories.

Documented provider behavior is not the same as a project guarantee. This
bootstrap records provider references for backup and snapshot inspection work;
future restore-drill validation remains deferred conceptual scope. No live
restore behavior exists in this repository.

## Provider Client Boundary

`LinodeApiClient` is the current live provider client and is read-only by
contract. It exists for inspection reads only. Its `request` method accepts
`GET` without a body; non-`GET` requests and request bodies are rejected before
the transport is called.

Future snapshot execution must introduce a separate mutation-specific provider
boundary in `src/linode_backup_lab/linode_api.py` rather than quietly adding
write helpers to `LinodeApiClient`. That first mutation boundary must keep
Linode API version and path handling centralized here, add focused tests for
its explicit mutation contract, and preserve public-safe reporting. Provider
`POST` behavior remains deferred; no mutation client, mutation helper, restore
helper, or mutation CLI exists yet.

## Snapshot Replacement Semantics

Official Akamai/Linode docs describe manual snapshots as a single manual
snapshot slot for a Linode. The Create a Linode using a backup workflow says a
snapshot backup can only have one current value and capturing a new one replaces
any existing snapshot backup. The manual snapshot guide likewise says taking a
new manual snapshot overwrites any previously saved manual snapshot.

Dry-run manifests therefore describe snapshot creation as having the
provider-documented side effect
`replaces_existing_manual_snapshot_for_linode`. Future live snapshot execution
must surface that side effect before allowing execution. This repository should
not describe manual snapshots as append-only history.

## Official References

- Linode API reference, List backups:
  <https://techdocs.akamai.com/linode-api/reference/get-backups>
- Linode API reference, Get a backup:
  <https://techdocs.akamai.com/linode-api/reference/get-backup>
- Linode API reference, Create a snapshot:
  <https://techdocs.akamai.com/linode-api/reference/post-snapshot>
- Linode API workflow, Create a Linode using a backup:
  <https://techdocs.akamai.com/linode-api/reference/create-a-linode-using-a-backup>
- Akamai Cloud Computing guide, Take a manual snapshot:
  <https://techdocs.akamai.com/cloud-computing/docs/take-a-manual-snapshot>

## Local Boundary

- Raw endpoint paths are built only in the API boundary.
- Raw provider response fields are normalized before command helpers consume
  them.
- The current live provider client is read-only and enforces `GET` without a
  request body.
- Stable internal resource concepts include `linode_id`, `backup_id`,
  `backup_label`, `backup_kind`, `snapshot_state`, and `backup_status`.
- No provider abstraction framework, API-version negotiation, mutation command,
  mutation provider client, restore execution, restore automation, or
  compatibility shim exists in this bootstrap.
- Public-facing manifests should prefer normalized project fields and avoid raw
  provider response bodies.
