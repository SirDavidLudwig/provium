# Provium

This repository is a Python monorepo containing two independently published
packages:

- [`packages/provium/`](packages/provium/) — the dependency-free core library.
- [`packages/provium-cli/`](packages/provium-cli/) — the command-line interface and command plugin
  system.

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

Each package retains its own `pyproject.toml`, tests, coverage gate, version,
and build metadata so it can be tested and released independently.
