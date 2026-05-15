# Governance and CI

This repository keeps governance lightweight and public-safe. Repository
settings live in hosted GitHub configuration; this file records the intended
settings so repo changes and hosted configuration can be reviewed separately.

## Current Workflows

The repo currently defines these GitHub Actions workflows:

- `.github/workflows/check.yml` runs on pull requests and pushes to `main`.
  It validates the declared Python support floor and current interpreter range
  with `make check` on Python 3.10, 3.11, 3.12, and 3.13. Its required status
  check names are:
  - `make check (Python 3.10)`
  - `make check (Python 3.11)`
  - `make check (Python 3.12)`
  - `make check (Python 3.13)`
- `.github/workflows/authoritative-source-check.yml` runs on pull requests.
  Its required status check name is
  `authoritative-source-check / authoritative-source-check`.

Do not rename either workflow job or the check workflow's Python matrix display
names without also updating hosted branch protection required status checks. The
display workflow names may appear as `Check` and `Authoritative Source Check`,
but branch protection should use the status check names listed above.

## Dependabot

`.github/dependabot.yml` enables weekly Dependabot updates for:

- GitHub Actions under `/`
- Python packaging metadata under `/`

Dependabot pull requests should pass the same required checks as other pull
requests before merge.

## Hosted Branch Protection

PR #26 added the workflow and Dependabot files, then left branch protection and
required status checks as a hosted GitHub follow-up. As of May 14, 2026, direct
repository inspection showed `main` was not protected.

The intended hosted branch protection for `main` is:

- require pull requests before merge;
- require status checks before merge;
- require these status checks:
  - `make check (Python 3.10)`
  - `make check (Python 3.11)`
  - `make check (Python 3.12)`
  - `make check (Python 3.13)`
  - `authoritative-source-check / authoritative-source-check`
- require branches to be up to date before merge when GitHub presents that
  option for the status-check rule;
- keep administrator bypass and review-count policy as an explicit repository
  owner decision.

Do not store secret values, private identifiers, non-public URLs, workplace
metadata, or token values in repository settings, workflow configuration,
Dependabot configuration, pull request text, or documentation. `LINODE_TOKEN`
may appear only as an environment variable name.

## Verification Commands

Use read-only GitHub commands to inspect hosted state before changing this
document or hosted settings:

```sh
gh pr view 26 --json number,title,state,body,statusCheckRollup,url
gh api repos/ctrl-alt-keith/linode-backup-lab/branches/main --jq '{name: .name, protected: .protected}'
gh api repos/ctrl-alt-keith/linode-backup-lab/actions/workflows --jq '.workflows[] | {name, path, state}'
```

Settings changes remain outside normal repository commits. Make the hosted
GitHub changes directly only when the repository owner has approved that
settings work.
