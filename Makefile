PYTHON ?= python
BUILD_PYTHON ?=
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

package-build: ## Build wheel and sdist, preferring an available build frontend.
	rm -rf "$(DIST_DIR)" "$(WHEEL_VENV)" "$(SDIST_VENV)" "$(PIPX_HOME_DIR)" "$(PIPX_BIN_DIR)" build
	@set -e; \
	if [ -n "$(BUILD_PYTHON)" ]; then \
		build_python="$(BUILD_PYTHON)"; \
		echo "Using BUILD_PYTHON=$$build_python; package-build will not bootstrap the build frontend."; \
	elif $(PYTHON) -m build --version >/dev/null 2>&1; then \
		build_python="$(PYTHON)"; \
		echo "Using existing build frontend from $(PYTHON); package-build will not bootstrap the build frontend."; \
	elif [ -x "$(BUILD_VENV)/bin/python" ] && "$(BUILD_VENV)/bin/python" -m build --version >/dev/null 2>&1; then \
		build_python="$(BUILD_VENV)/bin/python"; \
		echo "Using existing repo-local build venv at $(BUILD_VENV); package-build will not reinstall the build frontend."; \
	else \
		echo "No build frontend found for $(PYTHON). Bootstrapping $(BUILD_VENV)."; \
		echo "This fallback may require package-index access to install build and setuptools."; \
		rm -rf "$(BUILD_VENV)"; \
		$(PYTHON) -m venv "$(BUILD_VENV)"; \
		"$(BUILD_VENV)/bin/python" -m pip install "build>=1.0" "setuptools>=77"; \
		build_python="$(BUILD_VENV)/bin/python"; \
	fi; \
	"$$build_python" -m build --version >/dev/null || { \
		echo "Error: $$build_python must support 'python -m build'." >&2; \
		exit 1; \
	}; \
	if "$$build_python" -c 'import setuptools, sys; parts = tuple(int(part) for part in setuptools.__version__.split(".")[:2]); sys.exit(0 if parts >= (77,) else 1)' >/dev/null 2>&1; then \
		echo "Building with --no-isolation using the selected build environment."; \
		"$$build_python" -m build --no-isolation --outdir "$(DIST_DIR)"; \
	else \
		echo "Selected build environment lacks setuptools>=77; using build isolation."; \
		echo "This may require package-index access for build backend dependencies."; \
		"$$build_python" -m build --outdir "$(DIST_DIR)"; \
	fi

package-smoke: package-build ## Install built artifacts in isolated venvs and run help checks.
	$(PYTHON) -m venv "$(WHEEL_VENV)"
	"$(WHEEL_VENV)/bin/python" -m pip install "$(DIST_DIR)"/*.whl
	"$(WHEEL_VENV)/bin/linode-backup-lab" --help >/dev/null
	"$(WHEEL_VENV)/bin/linode-backup-lab" --version >/dev/null
	"$(WHEEL_VENV)/bin/python" -m linode_backup_lab --help >/dev/null
	"$(WHEEL_VENV)/bin/python" -m linode_backup_lab --version >/dev/null
	$(PYTHON) -m venv "$(SDIST_VENV)"
	@if "$(SDIST_VENV)/bin/python" -c 'import setuptools, sys; parts = tuple(int(part) for part in setuptools.__version__.split(".")[:2]); sys.exit(0 if parts >= (77,) else 1)' >/dev/null 2>&1; then \
		echo "Installing sdist with --no-build-isolation; sdist smoke will not bootstrap build backend dependencies."; \
		"$(SDIST_VENV)/bin/python" -m pip install --no-build-isolation "$(DIST_DIR)"/*.tar.gz; \
	else \
		echo "Sdist smoke environment lacks setuptools>=77; using pip build isolation."; \
		echo "This fallback may require package-index access for build backend dependencies."; \
		"$(SDIST_VENV)/bin/python" -m pip install "$(DIST_DIR)"/*.tar.gz; \
	fi
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
