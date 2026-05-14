# Releasing

Linode Backup Lab uses a lightweight release-prep process. The repository is
installable, smoke-testable, and changelog-driven, but release publishing stays
manual and human-gated through explicit Makefile targets.

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

`package-build` prefers a build frontend that is already available before it
bootstraps anything:

- Set `BUILD_PYTHON=/path/to/python` to use a prepared environment explicitly.
- Otherwise, `package-build` uses `$(PYTHON) -m build` when it is already
  available.
- If `.release-smoke/build-venv` already exists and can run `python -m build`,
  the target reuses it.
- Only when none of those paths can run `python -m build` does the target create
  `.release-smoke/build-venv` and install `build` plus `setuptools`.

When the selected build environment already has `setuptools>=77`,
`package-build` uses `python -m build --no-isolation` so the build itself does
not bootstrap backend dependencies. If backend dependencies are missing, it
falls back to build isolation and prints that package-index access may be
required.

The wheel install smoke does not bootstrap packaging tools. The sdist install
smoke also uses `--no-build-isolation` when the fresh smoke environment already
has `setuptools>=77`; otherwise it prints that pip build isolation may require
package-index access for backend dependencies.

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

## Release Lifecycle

Run the final local release readiness check before asking a human to publish:

```sh
make release-check VERSION=0.1.0
```

This target verifies GitHub CLI availability and authentication, runs
`make release-prep VERSION=0.1.0`, verifies that no local tag, remote tag, or
GitHub release already exists for `v0.1.0`, and confirms the expected wheel and
source distribution artifacts exist under `.release-smoke/dist/`.

After the release PR is merged and local `main` is current with `origin/main`,
the human-run publishing command is:

```sh
make release-publish VERSION=0.1.0
```

`release-publish` is the only Makefile target that performs the normal final
release action. It requires `main`, a clean working tree, current
`origin/main`, matching package and changelog versions, no existing tag, no
existing GitHub release, and freshly generated release-prep artifacts. It then
creates the annotated `v0.1.0` tag, pushes that tag, creates the GitHub release
from the changelog notes, and attaches these release assets:

- `.release-smoke/dist/linode_backup_lab-0.1.0.tar.gz`
- `.release-smoke/dist/linode_backup_lab-0.1.0-py3-none-any.whl`

If a release attempt is interrupted, inspect the partial state without mutating
remote state:

```sh
make release-recover VERSION=0.1.0
```

This reports local tag state, remote tag state, GitHub release state, whether
the expected wheel and source distribution artifacts are present, and any
suggested recovery command.

If the remote tag exists but the GitHub release is missing, recover by creating
the release from the existing tag:

```sh
make release-create-from-tag VERSION=0.1.0
```

This recovery target verifies GitHub CLI authentication, verifies the remote tag
exists, verifies the GitHub release does not already exist, runs release-prep to
ensure the wheel and source distribution artifacts exist, and creates the
GitHub release with those assets.

## Publishing Boundary

Release publishing is intentionally human-gated. The repository defines
Makefile targets for final tag and GitHub release publication, but no CI
workflow runs those targets automatically.

Routine release prep stops at validation and human review. Do not create tags,
GitHub releases, upload artifacts, publish to PyPI, or run provider-live release
validation unless a human explicitly runs the relevant release target. This
repository does not define PyPI publishing, provider-live release checks,
restore execution, live snapshot execution, scheduling, automatic remediation,
or desired-state management as part of release.
