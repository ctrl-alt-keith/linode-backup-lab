.PHONY: help check

.DEFAULT_GOAL := check

help: ## List available repo-local Makefile targets with short descriptions.
	@awk 'BEGIN {FS = ":.*## "}; /^[a-zA-Z0-9_.-]+:.*## / {printf "  %-24s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

check: ## Run canonical local validation.
	python -m compileall -q src tests
	PYTHONPATH=src python -m unittest discover -s tests/unit
