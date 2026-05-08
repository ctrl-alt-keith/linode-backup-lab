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
  configured snapshot label to the current provider snapshot label without
  emitting either raw label.
- `outcome` records runtime completion reporting separately from validation.
  Current dry-run plans report `not_executed`. `inspect` reports
  `provider_read_completed` only after the read-only provider request returns.
  Outcome objects also report `execution_state`, `partial_execution`,
  `state_uncertain`, `operator_review_required`, `retry_classification`,
  `idempotency_boundary`, and `retry_boundary` so operators do not have to infer
  retry posture from a status string.
- `safety` records decisions made by the command, including environment-only
  credentials, whether provider reads or mutations occurred, redaction posture,
  and cleanup state.

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
the current provider snapshot label, and whether local metadata appears stale.
Raw labels remain redacted from the emitted report.

Possible inspect states are:

- `provider_local_match`: the current provider snapshot label matches the
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

## Outcome State And Retry Vocabulary

Current commands expose only non-mutating retry classifications:

- `safe_to_rerun_no_provider_request`: no provider request was sent. Re-running
  repeats local validation and manifest generation only.
- `safe_to_rerun_read_only`: a read-only provider request completed. Re-running
  may observe newer provider state but does not mutate resources.

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

## CLI Exit Codes

- `0`: command succeeded and emitted a manifest.
- `1`: live provider read failed before a manifest could be emitted.
- `2`: usage, config, value, or local precondition failure, including missing
  required options, invalid config, unsupported values, or a missing
  environment-only credential required by the command.

No mutation-specific exit codes exist yet because no command performs live
mutations.
