# AGENTS.md

This repository uses the shared `ai-workflow-playbook` as the canonical source
for general workflow rules. This file is the thin repo-local execution layer.
Repo-local rules take precedence only for repo-specific behavior.

## Startup And Interaction Mode

- Start with `ai-workflow-playbook/docs/start-here.md` before repository or
  software work.
- Before acting, select the interaction mode from
  `ai-workflow-playbook/docs/repo-readiness.md`: implementation, review/audit,
  or orchestration/prompt-authoring.
- Implementation agents make explicit repo changes and carry them through
  validation, commit, push, and PR delivery.
- Review/audit agents inspect and report findings without mutating the repo.
- Orchestration/prompt-authoring agents produce complete, self-contained
  handoffs or prompts unless explicitly asked to implement.

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

## Local Execution

- Run commands from this repository working directory by default.
- Keep temporary workflow state repo-local, for example `.worktrees/`.
- Use direct command execution for ordinary repo commands such as `git ...`,
  `gh ...`, `make ...`, `python ...`, and repo-local scripts or tools.
- Before using `zsh`, `bash`, `sh`, `zsh -lc`, `bash -lc`, `sh -c`, aliases, or
  equivalent wrapper shells, check whether the command has a direct form and
  use that direct form when it does.
- Use shell wrappers only when shell syntax is genuinely required, such as
  pipelines, redirection, glob expansion, command chaining, scoped environment
  assignment, compound commands, or shell builtins.

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
- Live provider checks and credentialed checks are outside local blocking
  validation right now.
- No release automation or package publication workflow is currently
  documented for this repository.
- Keep validation implemented through the Makefile rather than direct tool
  invocation in normal workflow.

## Branches and PRs

- Branch from current `origin/main`.
- Follow the shared playbook branch naming guidance; use focused,
  purpose-based names such as `docs/<short-name>` or `feat/<short-name>`.
- Open PRs against `main`.
