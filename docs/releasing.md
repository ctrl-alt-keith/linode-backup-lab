# Releasing

Linode Backup Lab uses a lightweight release-prep process. The repository is
installable, smoke-testable, and changelog-driven, but release publishing stays
manual and human-gated.

## Scope

Release prep may validate packaging and install flows for the current project
scope:

- dry-run planning
- read-only inspect
- fixture replay
- public-safe reports

Release prep must not add or exercise restore execution, live snapshot
execution, scheduling, automatic remediation, desired-state management, provider
mutation, or credentialed live checks.

## Version And Changelog

- Keep the package version in `pyproject.toml` under `project.version`.
- Keep release notes in `CHANGELOG.md` under `## X.Y.Z`.
- Use `vX.Y.Z` only for the eventual Git tag name; Makefile release-prep targets
  accept either `X.Y.Z` or `vX.Y.Z` as `VERSION`.
- `linode-backup-lab --version` reads installed package metadata, with a source
  checkout fallback to `pyproject.toml`.

## Local Release Prep

Run the advisory release-prep target before a release PR is considered ready:

```sh
make release-prep VERSION=0.1.0
```

This target checks the changelog entry, verifies `pyproject.toml` has the same
version, runs canonical local validation through `make check`, builds a wheel
and source distribution into `.release-smoke/dist`, installs both artifacts into
isolated virtual environments, and verifies:

```sh
linode-backup-lab --help
linode-backup-lab --version
python -m linode_backup_lab --help
python -m linode_backup_lab --version
```

The target creates only repo-local generated state under `.release-smoke/`.
Generated release-prep output is intentionally ignored by git.

## Pipx Smoke

When `pipx` is available, run the advisory pipx smoke target:

```sh
make pipx-smoke
```

It installs the local checkout and then the built wheel into an isolated,
repo-local pipx home and verifies `linode-backup-lab --help` and
`linode-backup-lab --version` after each install. If `pipx` is unavailable,
report that blocker instead of substituting a normal virtual environment
install.

## Publishing Boundary

This repository does not currently define a Makefile target or CI workflow that
publishes to PyPI, creates a GitHub release, pushes a release tag, or performs
provider-live release validation.

For a future first release, stop after release-prep validation and human review
until an explicit publishing step is approved. Do not create tags, GitHub
releases, or package-index uploads as part of routine release prep.
