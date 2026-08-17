# Command-line tools

Installing Provium provides the `provium` command.

## Inspect an artifact

Display an artifact's metadata and lineage:

```bash
provium inspect result.pa
```

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
