# Provium

[![Tests](https://github.com/SirDavidLudwig/provium/actions/workflows/test.yml/badge.svg)](https://github.com/SirDavidLudwig/provium/actions/workflows/test.yml)
[![Documentation](https://github.com/SirDavidLudwig/provium/actions/workflows/docs.yml/badge.svg)](https://github.com/SirDavidLudwig/provium/actions/workflows/docs.yml)
[![codecov](https://codecov.io/gh/SirDavidLudwig/provium/graph/badge.svg)](https://codecov.io/gh/SirDavidLudwig/provium)

This repository is a Python monorepo containing the Provium package and its
example projects:

- [`packages/provium/`](packages/provium/) — the typed library, command-line
  interface, and command plugin system.
- [`examples/`](examples/) — installable example projects.

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
