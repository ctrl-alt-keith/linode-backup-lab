# Snapshot Execution Boundary

This note scopes a future explicit boundary for live manual snapshot execution.
It is design documentation only. It does not add a command, provider mutation
client, write helper, workflow runner, scheduler, retry loop, desired-state
reconciliation, remediation behavior, provider negotiation, or live snapshot
execution path.

Current repository behavior remains unchanged:

- `plan` and snapshot dry-run reporting describe a mutation-shaped snapshot
  request without reading or mutating provider state.
- `inspect` performs a read-only provider request and emits public-safe backup
  and snapshot state for operator review.
- `LinodeApiClient` remains a read-only inspection client and rejects non-`GET`
  requests.
- All current commands report provider mutations as `not_performed`.

## Future Mutation Boundary

The first live snapshot path must introduce a mutation-specific provider
boundary instead of extending the read-only inspection client with write
behavior. That boundary must keep provider API version handling and endpoint
path construction localized to the provider layer, with focused tests for the
mutation-specific contract.

A future command may request live execution only when all of these are true:

- The operator selected an explicit execution mode for this run. Dry-run output,
  manifest replay, config presence, and prior inspect output are not opt-in.
- The command performed or required a fresh inspect close enough to execution
  for the operator to review current provider snapshot state.
- The command surfaced that creating a manual snapshot replaces the existing
  manual snapshot for the Linode.
- Local validation passed, including the configured snapshot label and required
  environment-only credential presence.
- The emitted report can distinguish validation failure before request,
  request sent, provider response received, provider acceptance, provider
  failure after request, and ambiguous outcome.

This boundary must remain a narrow snapshot execution boundary. It must not add
scheduling, automatic remediation, restore behavior, provider negotiation,
multi-provider abstractions, desired-state management, or control-loop behavior.

## Operator Opt-In

Live snapshot execution must require a run-local, explicit operator opt-in. The
opt-in should be visible in command input and emitted reporting as separate
facts:

- execution was requested by the operator;
- execution was allowed after local validation and safety checks;
- execution was actually performed by the command.

These states map to the existing `mutation_intent` vocabulary described in
[`manifest-cli-contract.md`](manifest-cli-contract.md). They must stay separate
so a report can explain that a mutation was requested but blocked, allowed but
not reached, or attempted with uncertain provider outcome.

## Fresh Inspect Guidance

Future snapshot execution must assume dry-run state can be stale. The operator
should perform a fresh `inspect` before execution, and the execution report must
record whether the command used fresh backup-service state, skipped the read,
or could not establish stable manual snapshot-slot state.

Fresh inspect guidance is advisory and review-oriented. It must not become an
automatic reconciliation loop. If the fresh snapshot-slot comparison differs
from local config, the command should surface the mismatch and require operator
review instead of choosing whether local config or provider state wins. Fixture
replay and older inspect manifests are review aids only; they are not fresh
backup-service evidence for live execution.

## Manual Snapshot Replacement

Official Akamai/Linode docs describe manual snapshots as a single manual
snapshot slot for a Linode. A new manual snapshot replaces the existing manual
snapshot, and snapshot creation may take several minutes. The API summary lists
the snapshot creation operation as
`POST /{apiVersion}/linode/instances/{linodeId}/backups`.

A future execution design must therefore:

- present snapshot creation as replacement of the current manual snapshot, not
  append-only history;
- make replacement visible before live execution is allowed;
- keep the configured label as operator-facing intent, not as a unique provider
  history selector;
- avoid claiming completion until the command has explicit provider evidence for
  completion.

## Request And Response Uncertainty

Snapshot execution is a provider mutation and must report uncertainty without
guessing. Future reporting must distinguish at least these cases:

- no provider mutation request was sent;
- a provider mutation request was sent;
- a provider response was received;
- the provider accepted an asynchronous mutation request;
- the provider reported completed mutation success;
- local transport setup or preflight failed before the request was sent;
- a provider or transport failure occurred after the request may have been sent;
- the command cannot prove whether the provider received or accepted the
  request.

Any after-request failure or ambiguous outcome must set `state_uncertain: true`
and `operator_review_required: true` unless the command has explicit provider
evidence for a stronger final state. Retry classification remains reporting
metadata only; it must not trigger automatic retry, cleanup, remediation, or
reconciliation.

## Public-Safe Reporting

Future snapshot execution reports must remain public-safe. They may report
normalized command state, provider call shape, mutation posture, replacement
semantics, validation status, and uncertainty classification. They must not emit
secrets, authorization headers, raw provider response bodies, unnecessary
provider-identifying detail, or raw target values.

`LINODE_TOKEN` is environment-only. It may be named as the required environment
variable, but no token value may be read from config, echoed, persisted, or
included in fixtures.

## Non-Goals

This design note does not introduce or authorize:

- live snapshot execution in the current repository;
- restore execution or restore preflight approval;
- backup enablement, cancellation, or scheduling;
- automatic retries, cleanup, remediation, or recovery;
- provider negotiation or multi-provider abstractions;
- desired-state reconciliation or controller behavior;
- manifest replay as execution authorization.

## Official Provider References

- Akamai Cloud Computing guide, Take a manual snapshot:
  <https://techdocs.akamai.com/cloud-computing/docs/take-a-manual-snapshot>
- Akamai Cloud Computing guide, Get started with the Backups service:
  <https://techdocs.akamai.com/cloud-computing/docs/getting-started-with-the-linode-backup-service>
- Linode API summary:
  <https://techdocs.akamai.com/linode-api/reference/api-summary>
