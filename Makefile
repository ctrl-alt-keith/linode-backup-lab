PYTHON ?= python
RELEASE_VERSION = $(patsubst v%,%,$(VERSION))
RELEASE_SMOKE_DIR ?= .release-smoke
DIST_DIR = $(RELEASE_SMOKE_DIR)/dist
BUILD_VENV = $(RELEASE_SMOKE_DIR)/build-venv
WHEEL_VENV = $(RELEASE_SMOKE_DIR)/wheel-venv
SDIST_VENV = $(RELEASE_SMOKE_DIR)/sdist-venv
PIPX_HOME_DIR = $(abspath $(RELEASE_SMOKE_DIR)/pipx-home)
PIPX_BIN_DIR = $(abspath $(RELEASE_SMOKE_DIR)/pipx-bin)

.PHONY: help check release-notes release-prep package-build package-smoke pipx-smoke

.DEFAULT_GOAL := check

help: ## List available repo-local Makefile targets with short descriptions.
	@awk 'BEGIN {FS = ":.*## "}; /^[a-zA-Z0-9_.-]+:.*## / {printf "  %-24s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

check: ## Run canonical local validation.
	$(PYTHON) -m compileall -q src tests
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests/unit

release-notes: ## Print changelog release notes for VERSION.
	@if [ -z "$(VERSION)" ]; then \
		echo "Error: VERSION is required. Usage: make release-notes VERSION=0.1.0" >&2; \
		exit 1; \
	fi
	@if ! printf '%s\n' '$(RELEASE_VERSION)' | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$$'; then \
		echo "Error: VERSION must be X.Y.Z or vX.Y.Z." >&2; \
		exit 1; \
	fi
	@awk -v version='$(RELEASE_VERSION)' '\
		BEGIN { found = 0; printed = 0 } \
		$$0 == "## " version { found = 1; next } \
		found && /^## / { exit } \
		found { print; if ($$0 !~ /^[[:space:]]*$$/) printed = 1 } \
		END { \
			if (!found) { \
				printf "Error: CHANGELOG.md missing section ## %s.\n", version > "/dev/stderr"; \
				exit 1; \
			} \
			if (!printed) { \
				printf "Error: CHANGELOG.md section ## %s has no release notes.\n", version > "/dev/stderr"; \
				exit 1; \
			} \
		}' CHANGELOG.md

release-prep: ## Run advisory local release-prep checks for VERSION.
	@if [ -z "$(VERSION)" ]; then \
		echo "Error: VERSION is required. Usage: make release-prep VERSION=0.1.0" >&2; \
		exit 1; \
	fi
	@if ! printf '%s\n' '$(RELEASE_VERSION)' | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$$'; then \
		echo "Error: VERSION must be X.Y.Z or vX.Y.Z." >&2; \
		exit 1; \
	fi
	@$(MAKE) --no-print-directory release-notes VERSION='$(RELEASE_VERSION)' >/dev/null
	@$(PYTHON) -c 'import pathlib, sys; expected = "$(RELEASE_VERSION)"; text = pathlib.Path("pyproject.toml").read_text(encoding="utf-8"); marker = "version = " + repr(expected).replace(chr(39), chr(34)); sys.exit(0 if marker in text else "Error: pyproject.toml project.version must match VERSION=" + expected)'
	@$(MAKE) --no-print-directory check
	@$(MAKE) --no-print-directory package-smoke

package-build: ## Build wheel and sdist into repo-local release smoke output.
	rm -rf "$(RELEASE_SMOKE_DIR)"
	$(PYTHON) -m venv "$(BUILD_VENV)"
	"$(BUILD_VENV)/bin/python" -m pip install --upgrade pip build
	"$(BUILD_VENV)/bin/python" -m build --outdir "$(DIST_DIR)"

package-smoke: package-build ## Install built artifacts in isolated venvs and run help checks.
	$(PYTHON) -m venv "$(WHEEL_VENV)"
	"$(WHEEL_VENV)/bin/python" -m pip install --upgrade pip
	"$(WHEEL_VENV)/bin/python" -m pip install "$(DIST_DIR)"/*.whl
	"$(WHEEL_VENV)/bin/linode-backup-lab" --help >/dev/null
	"$(WHEEL_VENV)/bin/linode-backup-lab" --version >/dev/null
	"$(WHEEL_VENV)/bin/python" -m linode_backup_lab --help >/dev/null
	"$(WHEEL_VENV)/bin/python" -m linode_backup_lab --version >/dev/null
	$(PYTHON) -m venv "$(SDIST_VENV)"
	"$(SDIST_VENV)/bin/python" -m pip install --upgrade pip
	"$(SDIST_VENV)/bin/python" -m pip install "$(DIST_DIR)"/*.tar.gz
	"$(SDIST_VENV)/bin/linode-backup-lab" --help >/dev/null
	"$(SDIST_VENV)/bin/linode-backup-lab" --version >/dev/null
	"$(SDIST_VENV)/bin/python" -m linode_backup_lab --help >/dev/null
	"$(SDIST_VENV)/bin/python" -m linode_backup_lab --version >/dev/null

pipx-smoke: package-build ## Advisory pipx install smoke for checkout and built wheel.
	@command -v pipx >/dev/null 2>&1 || { echo "Error: pipx is required for make pipx-smoke but is not installed." >&2; exit 127; }
	PIPX_HOME="$(PIPX_HOME_DIR)" PIPX_BIN_DIR="$(PIPX_BIN_DIR)" pipx install --force .
	"$(PIPX_BIN_DIR)/linode-backup-lab" --help >/dev/null
	"$(PIPX_BIN_DIR)/linode-backup-lab" --version >/dev/null
	PIPX_HOME="$(PIPX_HOME_DIR)" PIPX_BIN_DIR="$(PIPX_BIN_DIR)" pipx install --force "$(DIST_DIR)"/*.whl
	"$(PIPX_BIN_DIR)/linode-backup-lab" --help >/dev/null
	"$(PIPX_BIN_DIR)/linode-backup-lab" --version >/dev/null
