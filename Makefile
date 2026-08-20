PYTHON ?= $(CURDIR)/.venv/bin/python

.PHONY: install test lint format-check type-check check docs build

install:
	$(PYTHON) -m pip install -e "./packages/provium[test,docs]"

test:
	cd packages/provium && $(PYTHON) -m pytest

lint:
	cd packages/provium && $(PYTHON) -m ruff check src test typecheck

format-check:
	cd packages/provium && $(PYTHON) -m ruff format --check src test typecheck

type-check:
	cd packages/provium && $(PYTHON) -m pyright

check: lint format-check type-check test

docs:
	$(PYTHON) -m mkdocs build --strict

build:
	$(PYTHON) -m build packages/provium --outdir dist/provium
