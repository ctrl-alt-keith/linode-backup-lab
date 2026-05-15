# Manifest And CLI Contract

This repository emits public-safe JSON manifests as report artifacts. They are
not a policy engine, state store, orchestration protocol, or automation input
contract.

## Manifest Vocabulary

- `dry_run` records whether the command intentionally avoided live provider
  reads and mutations for the operation being described. `dry_run: false` does
  not imply provider mutation; `inspect` is non-dry-run because it performs a
  live read-only provider request.
- `status` records the command-level report state, not provider resource
  lifecycle state. The shared manifest helper defaults non-dry-run shells to
  `initialized`; command helpers must set the emitted status, such as
  `inspected`, before returning a report.
- `provider_read` records live read state when a command performs a provider
  read. Plan and snapshot dry-runs record provider reads as `not_performed` in
  command and safety metadata instead of inventing a provider-read object.
  `inspect-replay` emits inspect-style backup state from an explicit sanitized
  fixture and records `provider_read.status: not_performed`.
- `command.provider_calls` is structured reporting metadata. `occurred` records
  whether any provider call was attempted, and `items` records each call's
  `kind`, `method`, and `operation` when calls occur. Callers should not parse
  operation state from a status string.
- Provider write/mutation state is recorded through planned action metadata and
  `safety.provider_mutations`. Current commands always report provider
  mutations as `not_performed`.
- `validation.status` records local config and command precondition checks. It
  is not a provider resource health verdict, provider completion report, or
  mutation gate. Advisory statuses such as
  `passed_with_unverified_provider_state`, `passed_with_uncertain_provider_state`,
  and `passed_with_drift_advisory` still mean the local command checks passed;
  they surface stale/drift risk for operator review.
- `state_assessment` records advisory local-vs-provider state visibility. Plan
  and snapshot dry-runs report `unverified_provider_state` because they do not
  perform provider reads. Inspect reports a fresh provider read and compares the
  configured snapshot label to the current manual snapshot slot label without
  emitting either raw label. Inspect replay reports fixture-derived visibility
  separately and does not claim that the fixture is live provider state.
- `outcome` records runtime completion reporting separately from validation.
  Current dry-run plans report `not_executed`. `inspect` reports
  `provider_read_completed` only after the read-only provider request returns,
  or `provider_read_failed` when the provider read cannot return usable backup
  state.
  `inspect-replay` reports `fixture_replay_completed` after reading a local
  fixture and performing no provider request.
  Outcome objects also report `execution_state`, `partial_execution`,
  `state_uncertain`, `operator_review_required`, `retry_classification`,
  `idempotency_boundary`, and `retry_boundary` so operators do not have to infer
  retry posture from a status string.
- `review` is a concise operator-facing packet derived from the detailed
  manifest fields. It summarizes provider calls, mutation posture, skipped or
  unknown normalized backup state, and retry/recovery posture for review. It is
  reporting metadata only, not orchestration state.
- `safety` records decisions made by the command, including environment-only
  credentials, whether provider reads or mutations occurred, redaction posture,
  and cleanup state.

## Shared Command Block

Every current emitted manifest with a `command` object includes this shared
required-field subset:

- `command.name`: the CLI command or command-shaped helper that produced the
  manifest.
- `command.config_source`: where project config came from. Current commands use
  `explicit` because `--config` is required.
- `command.config_path_recorded`: whether the local config path is emitted.
  Current public-safe manifests record `false`.
- `command.provider_calls`: structured provider-call metadata with `occurred`
  and `items`. Each item records the provider call `kind`, `method`, and
  `operation` when calls occur.

Commands may add command-specific fields, such as `token_source`,
`fixture_source`, or `fixture_path_recorded`, without changing this shared
subset. Current plan and snapshot dry-runs, live inspect reports, inspect
failure reports, and inspect replay reports all preserve this command subset.

## Validation Status Vocabulary

`validation.status` values are command precondition and review-status
summaries. They are not provider lifecycle states, restore approvals, mutation
gates, remediation decisions, or desired-state signals.

| Value | Emitted by | Trigger condition | Review meaning |
| --- | --- | --- | --- |
| `passed_with_unverified_provider_state` | `plan`; snapshot dry-run helper path (`snapshot_manifest(..., dry_run=True)`) | Local config and snapshot-label checks passed, but the command intentionally skipped live provider reads. | The manifest is a valid dry-run review artifact; provider backup state is unverified and a fresh `inspect` is required before any future mutation path. |
| `passed` | `inspect` success path (`create_inspect_manifest`) | Local inspect preconditions passed, the read-only provider request completed, and the current manual snapshot-slot label matched the configured snapshot label. | The live read supports the configured snapshot-slot comparison; this is still read-only evidence, not restore authorization or mutation approval. |
| `passed_with_drift_advisory` | `inspect` success path (`create_inspect_manifest`) | Local inspect preconditions passed and the provider read completed, but no current manual snapshot slot matched the configured snapshot label. | The command succeeded, but local config and visible provider state diverge or local metadata may be stale; operator review is required before relying on it for future work. |
| `passed_with_uncertain_provider_state` | `inspect` success path (`create_inspect_manifest`) | Local inspect preconditions passed and the provider read completed, but the current manual snapshot-slot comparison was not stable, such as when a snapshot is in progress or the current slot label was unavailable. | The command succeeded, but the provider snapshot-slot state cannot prove match or drift; refresh and operator review are needed before any future mutation path. |
| `provider_read_failed` | `inspect` provider-failure path (`create_inspect_failure_manifest`) | Local config and token preconditions passed, but the read-only provider request failed or did not return usable backup-service state. | The report is public-safe failure evidence; provider state remains uncertain and must be refreshed by a future successful `inspect` before any future mutation path. |
| `passed_with_fixture_replay` | `inspect-replay` success path (`create_replay_inspect_manifest`) | Local config and explicit sanitized fixture checks passed, and no live provider read was attempted. | The report demonstrates inspect-style shape from fixture data only; it is not evidence of current provider backup-service or manual snapshot-slot state. |

## Compatibility For Strict Consumers

Manifest `schema_version` records the baseline project manifest shape. Within a
supported schema version, new fields may be added to top-level manifests or
nested manifest objects when they preserve existing field names, meanings, and
types. Additive reporting fields do not require a new version by themselves.
This compatibility rule is intentionally narrow: it covers reporting additions,
not provider behavior changes, restore contracts, state-store semantics, or
automation protocols.

Consumers that parse manifests with strict models should validate the fields
they require, reject missing required fields or unsupported `schema_version`
values, and ignore unknown fields by default. Consumers that need visibility
into newly added reporting fields can compare a manifest object against their
known field set and record the extra names as additive fields for review.

The manifest helper exposes `BASE_MANIFEST_FIELDS`,
`manifest_required_view()`, and `manifest_additive_fields()` for this pattern.
The same approach applies to nested objects: keep a known field set for the
object being consumed, validate that subset, and treat extra fields as
extensions unless a future contract explicitly documents a breaking change.

Future schema-artifact work is tracked as additive groundwork in
[`schema-artifact-groundwork.md`](schema-artifact-groundwork.md). That document
inventories the current emitted manifest families and records the path toward
generated artifacts without making a generated schema part of the current
contract.

## Mutation Intent

`mutation_intent` separates four concepts that future mutation design must keep
distinct:

- `planned_operation`: the mutation-shaped operation described by the manifest,
  such as `snapshot_request`, or `null` when the command has no mutation-shaped
  operation.
- `execution_requested`: this run requested live mutation execution.
- `execution_allowed`: this run allowed live mutation execution after command
  validation and safety checks.
- `execution_performed`: this run actually performed a live mutation.

Current public-safe commands never request, allow, or perform live mutation
execution. `plan` and the snapshot helper describe a dry-run
`snapshot_request`; `inspect` uses `planned_operation: null` and remains
read-only. Future mutation execution must introduce an explicit
mutation-specific provider boundary and tests before any provider write
behavior is added; the current `LinodeApiClient` remains a read-only inspection
client.

## Snapshot Mutation Readiness

The project config preserves one explicit `target.snapshot_label` field. The
label is validated against the official Create a snapshot request body
constraint: a required string with length `1..255` after local whitespace
trimming.

Plan and snapshot dry-run manifests surface the provider-documented side effect
`replaces_existing_manual_snapshot_for_linode` on the planned snapshot action.
Official Akamai/Linode docs describe manual snapshot creation as replacing the
previous manual snapshot for that Linode, so the first live mutation manifest
must continue to surface that replacement side effect before execution can be
allowed. Snapshot manifests must not imply append-only manual snapshot history.

Plan and snapshot dry-runs also report provider state as unverified because
they intentionally avoid live provider reads. Their `state_assessment` marks
stale metadata as possible and includes refresh-before-mutation guidance. This
is advisory reporting only; no command currently uses it to perform or block a
provider mutation.

## Drift And Stale-State Visibility

`inspect` is the only current command that refreshes provider backup state. Its
`state_assessment` reports whether a current provider snapshot is present,
whether a snapshot is in progress, whether the configured snapshot label matches
the current manual snapshot slot label, and whether local metadata appears
stale.
Raw labels remain redacted from the emitted report.

Possible inspect states are:

- `provider_local_match`: the current manual snapshot slot label matches the
  configured snapshot label.
- `provider_local_mismatch`: the fresh provider read shows no matching current
  snapshot, which means local config and provider state diverge or local
  metadata is stale.
- `uncertain_provider_state`: the fresh provider read cannot support a stable
  comparison, such as when a snapshot is in progress or a current snapshot label
  is unavailable.

All current drift states are advisory-first. They improve review visibility and
refresh guidance without adding synchronization, automatic remediation, or
mutation behavior.

## Backup-Service And Snapshot-Slot Vocabulary

Current manifests use stable field names such as `provider_read`,
`normalized_backup_state`, `state_assessment.provider_local_match`, and
`configured_snapshot_label_matches_current`. Those fields describe two related
but separate review surfaces:

- Backup-service visibility: whether the command read the Linode backups
  collection, failed before usable backup-service state was available, skipped
  the provider entirely, or replayed a local fixture.
- Manual snapshot-slot comparison: whether the visible current manual snapshot
  slot can be compared with the configured `target.snapshot_label`.

`provider_local_match` is therefore not a general provider-health verdict. In a
successful live `inspect`, it only summarizes the configured label comparison
against the current manual snapshot slot visible in the backup-service read.
It does not compare automatic backups, restore readiness, source/target Linode
identity, region, storage, overwrite intent, disk UUIDs, or future mutation
permission.

`provider_local_mismatch` means the fresh live read did not show a current
manual snapshot slot matching the configured label. The manifest does not decide
whether local config, provider state, or operator intent should win.
`uncertain_provider_state` means the read cannot support a stable snapshot-slot
comparison, such as when a snapshot is in progress or the current slot label is
not available. `unverified_provider_state`, `provider_read_failed`, and
`fixture_replayed` likewise do not provide live snapshot-slot proof.

Failure reports and replay reports keep the same boundary explicit. A provider
failure report can say whether a read request was sent, but it does not contain
usable backup-service state. An `inspect-replay` report can demonstrate how
fixture values flow through inspect-style output, but it remains
`sanitized_fixture_replay` evidence rather than live backup-service evidence.

## Inspect Provider Failure Reports

If `inspect` passes local config and token preconditions but the read-only
provider request fails, the CLI exits with code `1` and emits a public-safe JSON
failure manifest instead of raw provider detail. The report records that the
provider read failed, whether a request was sent, whether a response was
received when known, and a coarse failure category such as `http_error`,
`network_error`, `invalid_json`, or `unexpected_json_shape`.

Failure metadata is conservative: generic or internal provider-boundary errors
do not claim a provider request was sent or a response was received unless the
provider client explicitly reports that evidence.

Failure reports do not include token values, target values, raw provider
payloads, provider URLs, authorization headers, backup identifiers, labels, or
provider timestamps. They also do not perform retry, recovery, cleanup, restore,
or mutation behavior. The failed provider state remains uncertain and must be
refreshed with a future successful `inspect` before any future mutation path is
allowed.

## Inspect Replay

`inspect-replay` is a non-live fixture path for generating inspect-style output
from an explicit sanitized normalized-backup fixture:

```sh
python -m linode_backup_lab inspect-replay \
  --config examples/backup-lab.example.toml \
  --fixture tests/fixtures/sanitized/inspect-provider-backups.normalized.json
```

Replay does not read provider state, does not require `LINODE_TOKEN`, does not
discover config or fixture paths, and does not record either path in the
manifest. It reports `command.provider_calls.occurred: false`,
`provider_read.status: not_performed`, `safety.provider_reads: not_performed`,
and `fixture_replay.live_provider_state_read: false`.

Replay fixtures must contain only public-safe normalized backup values. Raw
provider fields, provider identifiers, labels, timestamps, URLs, authorization
headers, raw provider response bodies, and token material are outside the replay
contract. Sensitive normalized fields should be `null` or use synthetic
placeholders such as `SANITIZED_*`. The fixture loader rejects obvious raw
provider fields and raw-looking fixture text as a lightweight safety check; it
does not validate live provider semantics.

Replay may compare the configured snapshot label to labels present in the
fixture for local demonstration, but `state_assessment.source` is
`sanitized_fixture_replay`, `fixture_local_match` is fixture-only, and
`provider_local_match` is `not_evaluated_live`. A replay report is never
evidence of current provider backup-service state or current manual
snapshot-slot state. Before any future mutation path, operators must run live
read-only `inspect` with an environment-provided `LINODE_TOKEN`.

## Outcome State And Retry Vocabulary

Current commands expose only non-mutating retry classifications:

- `safe_to_rerun_no_provider_request`: no provider request was sent. Re-running
  repeats local validation and manifest generation only. For `inspect-replay`,
  re-running also reads the explicit local fixture again.
- `safe_to_rerun_read_only`: a read-only provider request completed. Re-running
  may observe newer provider state but does not mutate resources.
- `safe_to_rerun_read_only_after_provider_failure`: a read-only provider
  request failed. Re-running retries the read-only request and does not mutate
  resources.

`review.retry_recovery` translates runtime outcome and provider state visibility
into two intentionally separate classifications:

- `command_retry_classification`: whether the command itself can be rerun. For
  current non-mutating commands this is `safe_to_retry`.
- `provider_state_classification`: what the refreshed or unrefreshed provider
  state implies before a future recovery-style retry or mutation attempt. This
  is advisory state posture only; it does not change whether the current command
  is safe to rerun.

Provider-state classifications are:

- `safe_to_retry`: a fresh read shows the current manual snapshot slot label
  matches the configured snapshot label. This removes the current
  snapshot-slot label-drift advisory from a future retry decision, but it is
  not restore authorization or mutation approval.
- `refresh_before_retry`: provider state was not read by this command, so a
  fresh `inspect` should happen before any future recovery-style retry or
  mutation attempt.
- `operator_review_required`: a fresh read shows the configured snapshot label
  and current manual snapshot slot diverge. The manifest does not choose
  whether local config, provider state, or operator intent should win.
- `state_uncertain`: the provider read cannot support a stable comparison, such
  as when a snapshot is in progress or the current snapshot label is not
  available.

`review.retry_recovery.automatic_retry` is always `not_performed` for current
commands. The classification is review guidance only; it does not enqueue,
schedule, or perform retry or recovery behavior.

No command performs live mutation yet. Before the first mutation path is added,
its report vocabulary needs to distinguish these states without turning the
manifest into a run database, remediation workflow, or orchestration protocol:

- `request_not_sent`: validation or safety checks prevented a provider mutation
  request before transport.
- `request_sent`: a provider mutation request was attempted.
- `provider_response_received`: the provider returned a response to the
  mutation request.
- `mutation_accepted`: the provider accepted an asynchronous mutation request.
- `mutation_succeeded`: the provider reported completed mutation success when
  the command has explicit evidence for that stronger state.
- `provider_failure_before_request`: local transport setup or preflight failed
  before a provider mutation request was sent.
- `provider_failure_after_request`: a provider request was sent and then failed
  with an error response or transport error.
- `ambiguous_outcome`: the command cannot prove whether the provider received
  or accepted the mutation request.

Any after-request mutation failure, partial execution, or `ambiguous_outcome`
must set `state_uncertain: true` and `operator_review_required: true` unless the
command has explicit provider evidence for a stronger final state. Retry
classification is advisory reporting only; it must not trigger automatic
recovery or remediation.

## Run Identity And Persistence

`run_id` is report metadata only. The project does not maintain a run database,
run history, state store, or retained orchestration handle. Manifests are emitted
artifacts; retaining, naming, or comparing them is the caller's responsibility.
`run_id` is not a primary key and must not be treated as proof that a prior run
exists.

## Inspect Boundaries

Inspect output is diagnostic reporting output. It summarizes public-safe
provider read results for review and debugging. It must not be treated as an
automatic control-loop input, desired-state signal, or mutation gate unless a
future design explicitly introduces and documents that behavior.

Inspect and inspect-replay reports include an additive `review_summary` object
for manual review. It provides a compact headline, sorted status counts, a
small state snapshot, and deterministic attention notes derived from existing
contract fields. Automation should continue to consume the stable structured
fields it already depends on, such as `inspection_summary`,
`normalized_backup_state`, `review`, `state_assessment`, `outcome`, and
`validation`.

The `review.state_visibility.unknown_fields` counts missing normalized provider
fields after redaction. For snapshot backups, `snapshot_state_for_snapshot`
counts snapshot records whose current/in-progress state was not known. Dry-run
commands do not read provider backup state, so their review packet reports
`provider_backup_state: not_read` and lists skipped read/mutation states.

## Restore Boundary

No restore command or restore manifest contract exists yet. Current `plan`,
`snapshot`, and `inspect` manifests must not be interpreted as restore
preflight approval, restore lineage proof, or permission to perform a provider
mutation. `backup_id`, source Linode identity, target Linode identity, target
region, storage availability, overwrite intent, disk UUIDs, and configuration
profile block-device assignments are not fully modeled by current public-safe
reports.

A future restore design must keep restore lineage explicit: the backup selected
for restore needs a source Linode and provider backup identifier, and the
restore target needs its own target Linode or new-Linode creation context.
Snapshot labels and backup labels are review aids only; they are not unique
restore selectors and must not replace provider identifiers in a restore
contract.

Restore collision and overwrite risks must be surfaced before execution is
allowed. At minimum, a future restore report needs to distinguish same-Linode
restore, new-Linode restore, overwrite and non-overwrite paths, unverified
storage/region prerequisites, and side-by-side disk access risks caused by
provider-preserved disk UUIDs. Modeling these risks must not add automatic
restore execution, remediation, or cleanup.

## CLI Exit Codes

- `0`: command succeeded and emitted a manifest.
- `1`: live provider read failed after local inspect preconditions passed. For
  `inspect`, the command emits a public-safe failure manifest on stdout and a
  sanitized one-line error on stderr.
- `2`: usage, config, value, or local precondition failure, including missing
  required options, invalid config, unsupported values, or a missing
  environment-only credential required by the command. Invalid or unreadable
  replay fixtures also return `2`.

No mutation-specific exit codes exist yet because no command performs live
mutations.
