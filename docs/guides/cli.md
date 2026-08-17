# Command-line tools

Installing Provium provides the `provium` command.

## Inspect an artifact

Display an artifact's metadata and lineage:

```bash
provium inspect result.pa
```

Use `--body` to request artifact-specific body details. Body inspection is
reported as unavailable when the artifact type cannot be discovered or its
reader does not provide an inspector:

```bash
provium inspect --body result.pa
```

## Dump an artifact

Create a portable directory containing `manifest.json` and the artifact's body
representation:

```bash
provium artifact dump result.pa result-dump/
```

With the default `--representation auto`, Provium uses the artifact's custom
`dump()` and `load()` methods when both are available. Otherwise it writes the
canonical body bytes to `body.dat`. You can require either behavior explicitly:

```bash
provium artifact dump result.pa result-dump/ --representation custom
provium artifact dump result.pa result-dump/ --representation raw
```

Use `--overwrite` to replace an existing dump destination:

```bash
provium artifact dump result.pa result-dump/ --overwrite
```

## Load an artifact

Reconstruct an artifact from a dump package:

```bash
provium artifact load result-dump/ restored.pa
```

The default `--mode exact` verifies that the reconstructed body has the original
length and SHA-256 digest. An exact load preserves the artifact identity and
lineage. Modified content is rejected.

To load intentionally modified content, choose its provenance policy explicitly:

```bash
# Preserve the original lineage and record a derived load.
provium artifact load edited-dump/ edited.pa --mode derived

# Drop the inherited lineage and create an unsafe-load provenance root.
provium artifact load edited-dump/ new-root.pa --mode root
```

The representation can be constrained during load, and an existing destination
can be replaced explicitly:

```bash
provium artifact load result-dump/ restored.pa \
    --representation custom \
    --overwrite
```

`--representation auto` loads the representation declared by the manifest.
`custom` requires a custom payload, while `raw` requires `body.dat`.

## Inspect and verify a dump

Inspect the package metadata and transfer-event count without loading it:

```bash
provium artifact inspect-dump result-dump/
```

Verify the manifest inventory, safe relative paths, file sizes, and SHA-256
digests:

```bash
provium artifact verify-dump result-dump/
```

Verification exits with a nonzero status and prints each detected error to standard
error when the package is invalid. See [Dumping and importing](transfers.md) for
the package model and Python API.

## Render a provenance graph

Write a Mermaid graph definition:

```bash
provium graph result.pa lineage.mmd
```

Graphviz output requires the optional visualization dependencies and a local
Graphviz installation:

```bash
python -m pip install "provium[visualization]"
provium graph --renderer graphviz result.pa lineage.png
```

Run `provium --help` or `provium <command> --help` for the complete set of
options supported by the installed release.
