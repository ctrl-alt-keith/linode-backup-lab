PYTHON ?= python
BUILD_PYTHON ?=
RELEASE_VERSION = $(patsubst v%,%,$(VERSION))
RELEASE_TAG = v$(RELEASE_VERSION)
RELEASE_SMOKE_DIR ?= .release-smoke
DIST_DIR = $(RELEASE_SMOKE_DIR)/dist
SDIST_ARTIFACT = $(DIST_DIR)/linode_backup_lab-$(RELEASE_VERSION).tar.gz
WHEEL_ARTIFACT = $(DIST_DIR)/linode_backup_lab-$(RELEASE_VERSION)-py3-none-any.whl
BUILD_VENV = $(RELEASE_SMOKE_DIR)/build-venv
WHEEL_VENV = $(RELEASE_SMOKE_DIR)/wheel-venv
SDIST_VENV = $(RELEASE_SMOKE_DIR)/sdist-venv
PIPX_HOME_DIR = $(abspath $(RELEASE_SMOKE_DIR)/pipx-home)
PIPX_BIN_DIR = $(abspath $(RELEASE_SMOKE_DIR)/pipx-bin)

.PHONY: help check check-gh-env release-notes release-prep package-build package-smoke pipx-smoke release-check release-recover release-create-from-tag release-publish

.DEFAULT_GOAL := check

help: ## List available repo-local Makefile targets with short descriptions.
	@awk 'BEGIN {FS = ":.*## "}; /^[a-zA-Z0-9_.-]+:.*## / {printf "  %-24s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

check: ## Run canonical local validation.
	$(PYTHON) -m compileall -q src tests
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests/unit

check-gh-env: ## Verify GitHub CLI availability and authentication.
	@command -v gh >/dev/null 2>&1 || { echo "Error: GitHub CLI (gh) is required but is not installed." >&2; exit 1; }
	@gh auth status >/dev/null 2>&1 || { echo "Error: GitHub CLI authentication is required. Run 'gh auth login' and try again." >&2; exit 1; }

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

release-check: check-gh-env ## Run final local release readiness checks for VERSION.
	@if [ -z "$(VERSION)" ]; then \
		echo "Error: VERSION is required. Usage: make release-check VERSION=0.1.0" >&2; \
		exit 1; \
	fi
	@if ! printf '%s\n' '$(RELEASE_VERSION)' | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$$'; then \
		echo "Error: VERSION must be X.Y.Z or vX.Y.Z." >&2; \
		exit 1; \
	fi
	@$(MAKE) --no-print-directory release-prep VERSION='$(RELEASE_VERSION)'
	@if git rev-parse --verify --quiet "refs/tags/$(RELEASE_TAG)" >/dev/null; then \
		echo "Error: local tag $(RELEASE_TAG) already exists." >&2; \
		exit 1; \
	fi
	@remote_tag_status=0; \
	git ls-remote --exit-code --tags origin "refs/tags/$(RELEASE_TAG)" >/dev/null 2>&1 || remote_tag_status=$$?; \
	if [ "$$remote_tag_status" -eq 0 ]; then \
		echo "Error: remote tag $(RELEASE_TAG) already exists." >&2; \
		exit 1; \
	elif [ "$$remote_tag_status" -ne 2 ]; then \
		echo "Error: unable to check remote tag $(RELEASE_TAG)." >&2; \
		exit 1; \
	fi
	@release_view=$$(gh release view "$(RELEASE_TAG)" 2>&1 >/dev/null); \
	release_status=$$?; \
	if [ "$$release_status" -eq 0 ]; then \
		echo "Error: GitHub release $(RELEASE_TAG) already exists." >&2; \
		exit 1; \
	elif ! printf '%s\n' "$$release_view" | grep -Eiq 'not found|could not find'; then \
		echo "Error: unable to check GitHub release $(RELEASE_TAG): $$release_view" >&2; \
		exit 1; \
	fi
	@test -f "$(SDIST_ARTIFACT)" || { echo "Error: expected sdist artifact missing: $(SDIST_ARTIFACT)" >&2; exit 1; }
	@test -f "$(WHEEL_ARTIFACT)" || { echo "Error: expected wheel artifact missing: $(WHEEL_ARTIFACT)" >&2; exit 1; }
	@echo "Release checks passed for $(RELEASE_TAG)."

release-recover: check-gh-env ## Inspect partial release state for VERSION.
	@if [ -z "$(VERSION)" ]; then \
		echo "Error: VERSION is required. Usage: make release-recover VERSION=0.1.0" >&2; \
		exit 1; \
	fi
	@if ! printf '%s\n' '$(RELEASE_VERSION)' | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$$'; then \
		echo "Error: VERSION must be X.Y.Z or vX.Y.Z." >&2; \
		exit 1; \
	fi
	@local_tag_state=missing; \
	if git rev-parse --verify --quiet "refs/tags/$(RELEASE_TAG)" >/dev/null; then \
		local_tag_state=exists; \
	fi; \
	remote_tag_state=missing; \
	remote_tag_status=0; \
	git ls-remote --exit-code --tags origin "refs/tags/$(RELEASE_TAG)" >/dev/null 2>&1 || remote_tag_status=$$?; \
	if [ "$$remote_tag_status" -eq 0 ]; then \
		remote_tag_state=exists; \
	elif [ "$$remote_tag_status" -eq 2 ]; then \
		remote_tag_state=missing; \
	else \
		echo "Error: unable to inspect remote tag $(RELEASE_TAG)." >&2; \
		echo "No automatic recovery action was taken." >&2; \
		exit 1; \
	fi; \
	release_state=missing; \
	release_view=$$(gh release view "$(RELEASE_TAG)" 2>&1 >/dev/null); \
	release_status=$$?; \
	if [ "$$release_status" -eq 0 ]; then \
		release_state=exists; \
	elif printf '%s\n' "$$release_view" | grep -Eiq 'not found|could not find'; then \
		release_state=missing; \
	else \
		echo "Error: unable to inspect GitHub release $(RELEASE_TAG): $$release_view" >&2; \
		echo "No automatic recovery action was taken." >&2; \
		exit 1; \
	fi; \
	sdist_state=missing; \
	wheel_state=missing; \
	if [ -f "$(SDIST_ARTIFACT)" ]; then \
		sdist_state=present; \
	fi; \
	if [ -f "$(WHEEL_ARTIFACT)" ]; then \
		wheel_state=present; \
	fi; \
	echo "Release recovery state for $(RELEASE_TAG):"; \
	echo "  local tag: $$local_tag_state"; \
	echo "  remote tag: $$remote_tag_state"; \
	echo "  GitHub release: $$release_state"; \
	echo "  sdist artifact: $$sdist_state ($(SDIST_ARTIFACT))"; \
	echo "  wheel artifact: $$wheel_state ($(WHEEL_ARTIFACT))"; \
	if [ "$$release_state" = "exists" ]; then \
		echo "Suggested recovery command: none; GitHub release $(RELEASE_TAG) already exists."; \
	elif [ "$$remote_tag_state" = "exists" ]; then \
		echo "Remote tag $(RELEASE_TAG) has already been published, but the GitHub release is missing."; \
		echo "Suggested recovery command:"; \
		echo "  make release-create-from-tag VERSION=$(RELEASE_VERSION)"; \
	elif [ "$$local_tag_state" = "exists" ]; then \
		echo "Local tag $(RELEASE_TAG) exists, but the remote tag and GitHub release are missing."; \
		echo "Suggested recovery command: none; inspect the local tag before manually deleting or pushing it."; \
	else \
		echo "No partial release publish state was found for $(RELEASE_TAG)."; \
		echo "Suggested recovery command: none; use make release-publish VERSION=$(RELEASE_VERSION) for the normal human-gated release."; \
	fi

release-create-from-tag: check-gh-env ## Create a missing GitHub release from an existing remote tag.
	@if [ -z "$(VERSION)" ]; then \
		echo "Error: VERSION is required. Usage: make release-create-from-tag VERSION=0.1.0" >&2; \
		exit 1; \
	fi
	@if ! printf '%s\n' '$(RELEASE_VERSION)' | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$$'; then \
		echo "Error: VERSION must be X.Y.Z or vX.Y.Z." >&2; \
		exit 1; \
	fi
	@remote_tag_status=0; \
	git ls-remote --exit-code --tags origin "refs/tags/$(RELEASE_TAG)" >/dev/null 2>&1 || remote_tag_status=$$?; \
	if [ "$$remote_tag_status" -eq 2 ]; then \
		echo "Error: remote tag $(RELEASE_TAG) does not exist. No release was created." >&2; \
		exit 1; \
	elif [ "$$remote_tag_status" -ne 0 ]; then \
		echo "Error: unable to inspect remote tag $(RELEASE_TAG). No release was created." >&2; \
		exit 1; \
	fi
	@release_view=$$(gh release view "$(RELEASE_TAG)" 2>&1 >/dev/null); \
	release_status=$$?; \
	if [ "$$release_status" -eq 0 ]; then \
		echo "Error: GitHub release $(RELEASE_TAG) already exists. No release was created." >&2; \
		exit 1; \
	elif ! printf '%s\n' "$$release_view" | grep -Eiq 'not found|could not find'; then \
		echo "Error: unable to inspect GitHub release $(RELEASE_TAG): $$release_view" >&2; \
		echo "No release was created." >&2; \
		exit 1; \
	fi
	@$(MAKE) --no-print-directory release-prep VERSION='$(RELEASE_VERSION)'
	@test -f "$(SDIST_ARTIFACT)" || { echo "Error: expected sdist artifact missing: $(SDIST_ARTIFACT)" >&2; exit 1; }
	@test -f "$(WHEEL_ARTIFACT)" || { echo "Error: expected wheel artifact missing: $(WHEEL_ARTIFACT)" >&2; exit 1; }
	@set -e; \
	notes_file=$$(mktemp); \
	trap 'rm -f "$$notes_file"' EXIT; \
	$(MAKE) --no-print-directory release-notes VERSION='$(RELEASE_VERSION)' > "$$notes_file"; \
	gh release create "$(RELEASE_TAG)" "$(SDIST_ARTIFACT)" "$(WHEEL_ARTIFACT)" --title "$(RELEASE_TAG)" --notes-file "$$notes_file" --verify-tag; \
	echo "Created GitHub release $(RELEASE_TAG) from existing remote tag."

release-publish: check-gh-env ## Human-gated publish of VERSION as a tag and GitHub release.
	@if [ -z "$(VERSION)" ]; then \
		echo "Error: VERSION is required. Usage: make release-publish VERSION=0.1.0" >&2; \
		exit 1; \
	fi
	@if ! printf '%s\n' '$(RELEASE_VERSION)' | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$$'; then \
		echo "Error: VERSION must be X.Y.Z or vX.Y.Z." >&2; \
		exit 1; \
	fi
	@if [ "$$(git branch --show-current)" != "main" ]; then \
		echo "Error: release publish must run from main after the release PR is merged." >&2; \
		exit 1; \
	fi
	@if [ -n "$$(git status --porcelain)" ]; then \
		echo "Error: working tree must be clean before release." >&2; \
		git status --short; \
		exit 1; \
	fi
	@git fetch origin main >/dev/null
	@if [ "$$(git rev-parse HEAD)" != "$$(git rev-parse origin/main)" ]; then \
		echo "Error: local main must match origin/main. Run 'git pull --ff-only origin main' and retry." >&2; \
		exit 1; \
	fi
	@$(MAKE) --no-print-directory release-notes VERSION='$(RELEASE_VERSION)' >/dev/null
	@$(PYTHON) -c 'import pathlib, sys; expected = "$(RELEASE_VERSION)"; text = pathlib.Path("pyproject.toml").read_text(encoding="utf-8"); marker = "version = " + repr(expected).replace(chr(39), chr(34)); sys.exit(0 if marker in text else "Error: pyproject.toml project.version must match VERSION=" + expected)'
	@if git rev-parse --verify --quiet "refs/tags/$(RELEASE_TAG)" >/dev/null; then \
		echo "Error: local tag $(RELEASE_TAG) already exists." >&2; \
		exit 1; \
	fi
	@remote_tag_status=0; \
	git ls-remote --exit-code --tags origin "refs/tags/$(RELEASE_TAG)" >/dev/null 2>&1 || remote_tag_status=$$?; \
	if [ "$$remote_tag_status" -eq 0 ]; then \
		echo "Error: remote tag $(RELEASE_TAG) already exists." >&2; \
		exit 1; \
	elif [ "$$remote_tag_status" -ne 2 ]; then \
		echo "Error: unable to check remote tag $(RELEASE_TAG)." >&2; \
		exit 1; \
	fi
	@release_view=$$(gh release view "$(RELEASE_TAG)" 2>&1 >/dev/null); \
	release_status=$$?; \
	if [ "$$release_status" -eq 0 ]; then \
		echo "Error: GitHub release $(RELEASE_TAG) already exists." >&2; \
		exit 1; \
	elif ! printf '%s\n' "$$release_view" | grep -Eiq 'not found|could not find'; then \
		echo "Error: unable to check GitHub release $(RELEASE_TAG): $$release_view" >&2; \
		exit 1; \
	fi
	@$(MAKE) --no-print-directory release-prep VERSION='$(RELEASE_VERSION)'
	@test -f "$(SDIST_ARTIFACT)" || { echo "Error: expected sdist artifact missing: $(SDIST_ARTIFACT)" >&2; exit 1; }
	@test -f "$(WHEEL_ARTIFACT)" || { echo "Error: expected wheel artifact missing: $(WHEEL_ARTIFACT)" >&2; exit 1; }
	@set -e; \
	notes_file=$$(mktemp); \
	trap 'rm -f "$$notes_file"' EXIT; \
	$(MAKE) --no-print-directory release-notes VERSION='$(RELEASE_VERSION)' > "$$notes_file"; \
	git tag -a "$(RELEASE_TAG)" -m "Release $(RELEASE_TAG)"; \
	git push origin "$(RELEASE_TAG)"; \
	gh release create "$(RELEASE_TAG)" "$(SDIST_ARTIFACT)" "$(WHEEL_ARTIFACT)" --title "$(RELEASE_TAG)" --notes-file "$$notes_file" --verify-tag; \
	echo "Published GitHub release $(RELEASE_TAG)."
