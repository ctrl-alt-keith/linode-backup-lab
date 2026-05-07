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
- Provider write/mutation state is recorded through planned action metadata and
  `safety.provider_mutations`. Current commands always report provider
  mutations as `not_performed`.
- `validation.status` records local config and command precondition checks. It
  is not a provider resource health verdict and is not a mutation gate.
- `safety` records decisions made by the command, including environment-only
  credentials, whether provider reads or mutations occurred, redaction posture,
  and cleanup state.

## Mutation Intent

`mutation_intent` separates four concepts that future mutation design must keep
distinct:

- `operator_intent_declared`: a config or command path describes an intended
  mutation target or operation. Dry-run planning can set this to `true` while
  still performing no execution.
- `execution_requested`: this run requested live mutation execution.
- `requested`: retained compatibility field with the same meaning as
  `execution_requested`.
- `allowed`: this run allowed live mutation execution after command validation
  and safety checks.
- `execution_performed`: this run actually performed a live mutation.

Current public-safe commands never request, allow, or perform live mutation
execution. `plan` and the snapshot helper declare operator intent for a dry-run
snapshot plan. `inspect` declares no mutation intent and remains read-only.
Future mutation execution must introduce an explicit mutation-specific provider
boundary and tests before any provider write behavior is added; the current
`LinodeApiClient` remains a read-only inspection client.

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
