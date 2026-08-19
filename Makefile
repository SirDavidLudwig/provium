PYTHON ?= $(CURDIR)/.venv/bin/python

.PHONY: install test lint format-check check docs build

install:
	$(PYTHON) -m pip install -e "./packages/provium[test,docs]" -e "./packages/provium-cli[test]"

test:
	cd packages/provium && $(PYTHON) -m pytest
	cd packages/provium-cli && $(PYTHON) -m pytest

lint:
	cd packages/provium && $(PYTHON) -m ruff check src test
	cd packages/provium-cli && $(PYTHON) -m ruff check src test

format-check:
	cd packages/provium && $(PYTHON) -m ruff format --check src test
	cd packages/provium-cli && $(PYTHON) -m ruff format --check src test

check: lint format-check test

docs:
	$(PYTHON) -m mkdocs build --strict

build:
	$(PYTHON) -m build packages/provium --outdir dist/provium
	$(PYTHON) -m build packages/provium-cli --outdir dist/provium-cli
