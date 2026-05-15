# Schema Artifact Groundwork

This document records the current manifest contract surface and the conservative
path toward future schema artifacts. It is groundwork, not a generated schema,
not a new validation gate, and not a promise that the manifest contract is ready
for hard external enforcement.

The authoritative contract sources remain:

- emitted manifests from `src/linode_backup_lab/`;
- regression coverage in `tests/unit/test_manifest_contracts.py`;
- replay-safe fixtures under `tests/fixtures/sanitized/`;
- operator-facing vocabulary in `docs/manifest-cli-contract.md`.

Future schema artifacts should be generated only after these sources agree on a
stable shape. Fixtures and replay tests should stay the practical reference for
edge cases and compatibility examples.

## Current Top-Level Inventory

All current manifests share the base fields:

- `schema_version`
- `provider`
- `run_id`
- `created_at`
- `action`
- `dry_run`
- `status`
- `resources`

Current `plan` and dry-run `snapshot` reports add:

- `command`
- `config`
- `planned_actions`
- `review`
- `mutation_intent`
- `state_assessment`
- `outcome`
- `validation`
- `safety`

Current successful `inspect` reports add:

- `command`
- `config`
- `provider_read`
- `provider_documented_fields`
- `inspection_summary`
- `review_summary`
- `normalized_backup_state`
- `review`
- `mutation_intent`
- `state_assessment`
- `outcome`
- `validation`
- `safety`

Current `inspect` provider-failure reports add:

- `command`
- `config`
- `provider_read`
- `inspection_summary`
- `review_summary`
- `normalized_backup_state`
- `review`
- `mutation_intent`
- `state_assessment`
- `outcome`
- `validation`
- `safety`

Current `inspect-replay` reports add:

- `command`
- `config`
- `provider_read`
- `provider_documented_fields`
- `fixture_replay`
- `inspection_summary`
- `review_summary`
- `normalized_backup_state`
- `review`
- `mutation_intent`
- `state_assessment`
- `outcome`
- `validation`
- `safety`

The stable shared subset is intentionally smaller than the full emitted object.
Strict consumers should validate the fields they require and treat unknown
fields as additive extensions within the same supported `schema_version`.

## Stability Map

Stable within `schema_version = "1"`:

- base manifest fields from `BASE_MANIFEST_FIELDS`;
- `command.provider_calls` shape with `occurred` and `items`;
- public-safe redaction posture for targets, identifiers, labels, timestamps,
  token material, provider URLs, and raw provider payloads;
- separation between `validation`, `outcome`, `state_assessment`, `review`,
  and `safety`;
- read-only inspect and non-live inspect replay semantics.

Additive-only candidates:

- new top-level reporting packets derived from existing fields;
- new nested fields inside existing packets when names, meanings, and types of
  existing fields are preserved;
- new sanitized fixtures that exercise existing replay semantics;
- additional advisory status vocabulary that remains non-mutating and
  documented before release.

Breaking or governance-level candidates:

- removing or renaming existing fields;
- changing a field type or meaning;
- treating `review_summary` as the automation contract instead of a manual
  review aid;
- turning manifests into state-store records, orchestration handles,
  remediation inputs, restore approvals, or desired-state signals;
- adding live provider mutation, restore execution, scheduling, or automatic
  retry behavior.

## Candidate Artifact Direction

The first generated artifact should be an advisory schema for emitted report
shape, not an execution policy. A future generator should start from explicit
field inventories and contract tests, then emit a schema artifact that:

- requires only the stable shared subset by default;
- allows additive fields unless a future version explicitly narrows that rule;
- models command families separately where their top-level packets differ;
- records public-safe redaction expectations as documentation, not as proof that
  arbitrary external payloads are sanitized;
- keeps project manifest `schema_version` separate from Linode provider API
  versioning.

JSON Schema is a reasonable candidate because it can describe object shape and
additive-field policy without adding a runtime dependency. A Python-only
artifact, such as typed dictionaries or dataclass views, may be useful for
internal helper code but should not replace a portable report artifact if the
repo later publishes machine-readable schema files.

Schema generation should not infer contract guarantees only from one golden
example. The fixture corpus intentionally includes missing optional fields,
status transitions, in-progress snapshots, unknown provider values, malformed
provider timestamps, and sparse normalized records. Those cases should feed
schema examples and compatibility tests before any artifact is presented as
stable.

## Scaffolding Path

1. Keep `manifest_required_view()` and `manifest_additive_fields()` as the
   consumer-side compatibility pattern.
2. Maintain this inventory alongside `tests/unit/test_manifest_contracts.py`.
3. Add a small generator only when there is a concrete artifact target, such as
   `docs/artifacts/manifest.schema.json`.
4. Generate into a reviewable path and keep generated output deterministic.
5. Validate generated artifacts through `make check`; do not add a separate
   local validation path.
6. Treat fixture replay and emitted manifest tests as the reference examples for
   schema compatibility.

## Current Risks And Stop Conditions

Do not generate or enforce schema artifacts yet if any of these are true:

- top-level packet names or nested status vocabulary are still changing;
- replay fixtures expose unresolved ambiguity;
- provider normalization behavior is being redesigned;
- a schema would imply restore, mutation, orchestration, scheduler, or
  remediation semantics that the repo intentionally does not implement;
- a generated artifact would require broad refactoring of manifest production
  code instead of documenting current behavior.

The next schema-artifact PR should be additive and reviewable on its own. It
should not combine schema generation with provider mutation, restore behavior,
or broad manifest redesign.
