# AGENTS.md

This repository uses the shared `ai-workflow-playbook` as the canonical source
for general workflow rules. This file is the thin repo-local execution layer.
Repo-local rules take precedence only for repo-specific behavior.

## Repo Scope

- This repo contains a public-safe Linode Backup Lab scaffold.
- Keep implementation lightweight and explicitly safety-oriented.
- Do not add live restore behavior, multi-provider support, provider
  negotiation, scheduling engines, automatic remediation, or desired-state
  management until a later milestone asks for it.

## File Placement

- Put source code under `src/linode_backup_lab/`.
- Put unit tests under `tests/unit/`.
- Put repo documentation under `docs/`.
- Put sanitized fixtures under `tests/fixtures/sanitized/`.

## Provider Assumptions

- Before changing behavior, docs, tests, or user-facing claims that depend on
  Linode provider semantics, verify the assumption against official Linode or
  Akamai API documentation.
- Keep provider API versions, raw endpoint paths, provider enum quirks, and raw
  nested response handling localized to the provider/API boundary.
- Keep project config schema versioning separate from provider API versioning.
- When relevant, cite or summarize verified official sources in PR notes or
  docs.

## Public-Safe Boundary

- Treat every file as public.
- Do not commit secret values, private identifiers, non-public URLs, or
  workplace metadata.
- `LINODE_TOKEN` may appear only as an environment variable name.
- Fixtures must be sanitized and live under `tests/fixtures/sanitized/`.

## Validation

- Use `make check` as the canonical validation entrypoint.
- `make check` runs Python compile checks for `src` and `tests`.
- `make check` runs the unit test suite under `tests/unit`.
- Live provider checks, credentialed checks, and release checks are outside
  local blocking validation right now.
- Keep validation implemented through the Makefile rather than direct tool
  invocation in normal workflow.

## Branches and PRs

- Branch from current `origin/main`.
- Use focused branch names such as `codex/provider-api-versioning`.
- Open PRs against `main`.
