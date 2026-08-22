# Provium

[![Documentation](https://github.com/Project-Provium/provium/actions/workflows/docs.yml/badge.svg)](https://github.com/Project-Provium/provium/actions/workflows/docs.yml)
[![codecov](https://codecov.io/gh/Project-Provium/provium/graph/badge.svg)](https://codecov.io/gh/Project-Provium/provium)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/Project-Provium/provium/blob/main/LICENSE)

Provium is a provenance-first Python framework for building trustworthy,
reproducible data workflows. It records how artifacts were produced as part of
normal execution, connecting each result to the procedure, inputs, and execution
that created it.

Instead of treating lineage as separate documentation that can drift out of
date, Provium makes provenance part of the workflow itself. The result is an
auditable history that helps teams understand where data came from, reproduce
past work, and inspect dependencies with confidence.

[Read the documentation](https://project-provium.github.io/provium/) to get
started and explore the complete guides and API reference.

## What Provium provides

- **Provenance-aware artifacts** that retain their production history.
- **Typed procedures** for defining clear, reusable units of work.
- **Reproducible execution** with recorded inputs, outputs, and identities.
- **Lineage inspection and visualization** through Python and the command line,
  including Graphviz and Mermaid output.
- **Extensible tooling** through a typed library, CLI, and command plugin system.

## Repository layout

- [`packages/provium/`](packages/provium/) — the Provium library, command-line
  interface, and tests.
- [`examples/`](examples/) — installable projects demonstrating Provium in use.
- [`docs/`](docs/) — guides, concepts, and reference documentation.

## Development

Create or activate the repository-level virtual environment, then install both
packages in editable mode:

```bash
python3 -m venv .venv
source .venv/bin/activate
make install
```

Run all checks from the repository root:

```bash
make check
```

Build the shared documentation site into `site/`:

```bash
make docs
```

The Provium package owns its `pyproject.toml`, tests, coverage gate, version,
and build metadata; examples remain separate projects in the monorepo.
