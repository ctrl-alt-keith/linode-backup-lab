# Restore Drill Design Sketch

This is a non-executable design sketch for future restore-drill validation. It
does not define a command, manifest contract, provider client, preflight
executor, automation workflow, cleanup workflow, or restore mutation path.

## Current Boundary

The current `plan`, `snapshot`, and `inspect` reports are review artifacts only.
They are not restore authorization, restore preflight approval, restore lineage
proof, or permission to perform a provider mutation.

Current reports intentionally do not fully model:

- source Linode identity for a restore lineage
- selected provider backup identity
- target Linode or new-Linode creation context
- target region
- available unallocated storage
- overwrite intent
- disk UUIDs
- configuration profile block-device assignments

Snapshot labels and backup labels can help an operator review visible state, but
labels are not unique restore selectors. A future restore drill must preserve
provider identifiers and restore lineage explicitly instead of selecting a
backup from a label match.

## Conceptual Review Model

A future restore-drill review design should model these inputs before any live
restore mutation is considered:

- `source_linode`: the Linode whose backup is being restored.
- `selected_backup`: the provider backup selected by backup ID, including its
  source Linode relationship, backup kind, availability, completion status,
  region, disk sizes, and config count where provider data is available.
- `restore_target`: either an existing target Linode or a proposed new-Linode
  creation context. The target must remain separate from the source, even when
  they refer to the same Linode.
- `lineage`: an explicit source Linode plus selected provider backup ID plus
  restore target relationship. Labels may be recorded as advisory display
  metadata, but never as unique selectors.
- `same_region_prerequisite`: whether the target region is known and matches
  the backup region. Unknown region state should stay unknown, not pass.
- `storage_prerequisite`: whether the target has enough unallocated storage for
  the restored disks when using a non-overwrite restore path. Unknown storage
  state should stay unknown, not pass.
- `overwrite_intent`: an explicit operator choice, separate from provider
  defaults. The design must distinguish overwrite from add-restored-disks
  behavior before execution is possible.
- `uuid_collision_risk`: whether original and restored disks might be mounted
  side by side with provider-preserved disk UUIDs, including the same-Linode
  and configuration-profile block-device assignment risks.

The model should treat missing provider facts as review blockers or unresolved
unknowns. It should not infer target readiness from the presence of a current
manifest, a successful inspect report, or a stale backup list.

## Restore Target Shapes

An existing-Linode target requires a target Linode identity that is separate
from the source backup path. The future review model needs to show whether the
target is the source Linode, a different Linode in the same region, or an
unknown/unverified target. It also needs to show whether the operator intends to
overwrite existing disks/configs or add restored disks alongside existing ones.

A new-Linode target requires a proposed creation context instead of an existing
target Linode ID. At minimum, that context needs the selected `backup_id`,
region, and type/plan choice. Optional Linode settings must be reviewed
separately because provider restore-from-backup behavior does not preserve every
Linode setting.

Both target shapes must keep restore lineage explicit:

- source Linode ID from the backup collection or backup path
- selected provider backup ID
- target existing Linode ID or new-Linode creation context
- region evidence for the backup and target
- overwrite or non-overwrite intent where applicable

## Risk Review

The future restore drill should surface these risks without performing a restore
or cleanup:

- Same-region prerequisite is unverified or mismatched.
- Non-overwrite restore does not have verified free storage for restored disks.
- Overwrite intent would delete target disks and configs if later executed.
- Same-Linode or side-by-side access could expose disk UUID collisions when the
  original and restored disks are mounted together.
- File-level recovery still requires restoring the backup first, then copying
  files from the restored Linode or disk; it is not a direct backup download or
  provider-side single-file restore.
- Restore-from-backup to a new Linode carries over disks, configuration, and
  `root_pass`, while other optional settings require separate review.

Risk review is advisory documentation for a future design. It must not schedule,
retry, remediate, delete, resize, migrate, restore, or otherwise mutate provider
resources.

## Explicit Non-Goals

This sketch does not add or specify:

- a `restore` command
- a restore manifest
- a restore provider client
- preflight execution
- provider mutation execution
- restore automation
- cleanup automation
- scheduling
- automatic remediation
- provider negotiation
- multi-provider abstractions
- desired-state behavior

## Provider Source Notes

Official Akamai/Linode docs describe restore as provider mutation behavior. The
Restore a backup API operation is a `POST` using a source Linode backup path
with source `linodeId` and `backupId`; its request body requires target
`linode_id` and accepts `overwrite`. The API docs also state that backups cannot
be restored across regions, successfully completed backups are required, and a
target Linode cannot currently be the target of a backup.

The existing-Linode restore guide says the target must be in the same data
center as the backup and must have enough free storage for restored disks unless
the operator chooses an overwrite path. It also says restore creates new disks
and a new configuration profile when not overwriting, and that restore is
whole-disk recovery rather than single-file selection.

The new-Linode-from-backup workflow requires selecting a provider backup ID and
creating the Linode in the same region with an adequate type/plan. It notes that
disks, configuration, and `root_pass` are carried over, while other optional
settings are reset or defaulted and need separate review.

The local-backup download guide states that backup contents are not directly
downloadable from the Backups service. Accessing backup contents requires first
restoring the backup to a new or existing Linode, then copying files or disk data
from that restored environment.

Official restore docs also warn that restored disks can preserve the original
disk UUID. Mounting the original disk and corresponding restored disk at the
same time can create a UUID collision, so future review must surface this before
any side-by-side disk access workflow.

References:

- <https://techdocs.akamai.com/linode-api/reference/post-restore-backup>
- <https://techdocs.akamai.com/linode-api/reference/create-a-linode-using-a-backup>
- <https://techdocs.akamai.com/cloud-computing/docs/restore-a-backup-to-an-existing-compute-instance>
- <https://techdocs.akamai.com/cloud-computing/docs/download-backups-locally>
