PYTHON ?= $(CURDIR)/.venv/bin/python

.PHONY: install test lint format-check type-check check docs build

install:
	$(PYTHON) -m pip install -e "./packages/provium[test,docs]"
	$(PYTHON) -m pip install -e "./examples/provium-text-pipeline[test]"

test:
	cd packages/provium && $(PYTHON) -m pytest
	cd examples/provium-text-pipeline && $(PYTHON) -m pytest

lint:
	cd packages/provium && $(PYTHON) -m ruff check src test typecheck
	cd examples/provium-text-pipeline && $(PYTHON) -m ruff check src test

format-check:
	cd packages/provium && $(PYTHON) -m ruff format --check src test typecheck
	cd examples/provium-text-pipeline && $(PYTHON) -m ruff format --check src test

type-check:
	cd packages/provium && $(PYTHON) -m pyright

check: lint format-check type-check test

docs:
	$(PYTHON) -m mkdocs build --strict

build:
	$(PYTHON) -m build packages/provium --outdir dist/provium
