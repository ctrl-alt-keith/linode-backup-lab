# Governance and CI

This repository keeps governance lightweight and public-safe. Repository
settings live in hosted GitHub configuration; this file records the intended
settings so repo changes and hosted configuration can be reviewed separately.

## Current Workflows

The repo currently defines these GitHub Actions workflows:

- `.github/workflows/check.yml` runs on pull requests and pushes to `main`.
  It validates the current supported Python version with `make check` on
  Python 3.13. Its required status check name is:
  - `make check`
- `.github/workflows/authoritative-source-check.yml` runs on pull requests.
  Its required status check name is
  `authoritative-source-check / authoritative-source-check`.

Do not rename either workflow job without also updating hosted branch
protection required status checks. The display workflow names may appear as
`Check` and `Authoritative Source Check`, but branch protection should use the
status check names listed above.

## Dependabot

`.github/dependabot.yml` enables weekly Dependabot updates for:

- GitHub Actions under `/`
- Python packaging metadata under `/`

Dependabot pull requests should pass the same required checks as other pull
requests before merge.

## Hosted Branch Protection

Hosted branch protection is configured in GitHub rather than in tracked
repository files. Direct repository inspection on July 6, 2026 showed `main` is
protected.

The current hosted branch protection for `main` is:

- require pull requests before merge;
- require status checks before merge;
- require these status checks:
  - `make check`
  - `authoritative-source-check / authoritative-source-check`
- do not require branches to be up to date before merge;
- allow administrator bypass;
- require zero approving reviews.

Keep changes to these settings explicit and source-verified. In this
solo-operator repository, status checks and pull request reviewability are the
primary integrity controls; review-count, strict-up-to-date, and administrator
bypass settings are repository owner decisions rather than repo-local workflow
defaults.

Do not store secret values, private identifiers, non-public URLs, workplace
metadata, or token values in repository settings, workflow configuration,
Dependabot configuration, pull request text, or documentation. `LINODE_TOKEN`
may appear only as an environment variable name.

## Verification Commands

Use read-only GitHub commands to inspect hosted state before changing this
document or hosted settings:

```sh
gh pr view 53 --json number,title,state,body,statusCheckRollup,url
gh api repos/ctrl-alt-keith/linode-backup-lab/branches/main --jq '{name: .name, protected: .protected}'
gh api repos/ctrl-alt-keith/linode-backup-lab/actions/workflows --jq '.workflows[] | {name, path, state}'
```

Settings changes remain outside normal repository commits. Make the hosted
GitHub changes directly only when the repository owner has approved that
settings work.
