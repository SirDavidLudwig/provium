# Provenance graphs

Provium can visualize the complete lineage stored in an artifact header. Artifact
nodes are square, procedure execution nodes are rounded, and directed edges show
which artifacts each execution consumed and produced.

By default, labels contain artifact identifiers and procedure names only. Hashes
are available when they are useful for auditing or debugging.

## Render an image

Pass an artifact and the destination image path to `graph render`:

```bash
provium graph render results.pa lineage.svg
```

The output suffix selects the image format. Provium passes that suffix to the
selected backend, which decides whether it is supported. When the output has no
suffix, Provium appends `.png`:

```bash
provium graph render results.pa lineage
# Writes lineage.png
```

The default `--backend auto` tries Graphviz first and then Mermaid when Graphviz
is unavailable or does not support the requested format. Select a backend
strictly when reproducibility matters:

```bash
provium graph render results.pa lineage.svg --backend graphviz
provium graph render results.pa lineage.png --backend mermaid
```

An explicitly selected backend reports its own missing-dependency or
unsupported-format error. Automatic selection does not hide an execution
failure from an installed backend that supports the requested format.

Rendered image bytes are always written to the output file; they are never sent
to standard output.

## Generate DOT or Mermaid source

Use `graph source` when you want editable graph code rather than an image. The
source language is an explicit positional argument:

```bash
provium graph source results.pa dot lineage.dot
provium graph source results.pa mermaid lineage.mmd
```

The optional output path is used exactly as provided. Provium does not append or
validate its extension.

Omit the output path to write source to standard output. This makes redirection
and pipelines safe:

```bash
provium graph source results.pa mermaid > lineage.mmd
provium graph source results.pa dot | dot -Tsvg > lineage.svg
```

Prompts and diagnostics are written to standard error, so redirected graph
source remains valid.

## Include identities and versions

No hashes are shown by default. Add any combination of these options to
`render` or `source`:

| Option | Short form | Label content |
| --- | --- | --- |
| `--show-artifact-identities` | `-a` | Artifact identity hash |
| `--show-procedure-versions` | `-p` | Procedure version hash |
| `--show-execution-identities` | `-e` | Execution identity hash |

For example:

```bash
provium graph render results.pa lineage.png -a -p -e
provium graph source results.pa mermaid -p -e
```

Artifact identifiers and procedure names remain visually prominent. Optional
identity and version values use explicit labels and monospaced hash text.

## Replace an existing output

Provium asks before replacing an existing image or source file. Pass `-y` to
confirm without a prompt:

```bash
provium graph render results.pa lineage.png -y
provium graph source results.pa dot lineage.dot -y
```

In a non-interactive environment, an existing output causes the command to fail
without modifying the file unless `-y` is present. This makes CI behavior
explicit and prevents accidental replacement.

## Install a rendering backend

Source generation has no Graphviz or Mermaid dependency. Rendering loads its
integration only when selected.

Graphviz rendering requires both the optional Python package and a Graphviz
executable on `PATH`. Install the Python integration with:

```bash
python -m pip install "provium[graphviz]"
```

Install Graphviz itself using the package manager for your operating system.

Mermaid rendering requires the `mmdc` executable from Mermaid CLI on `PATH`.
The Mermaid backend renders PNG, SVG, and PDF files. Backend-supported Graphviz
formats are determined by the installed Graphviz package.

## Python API

The source generators and backend selector are also available from Python:

```python
from pathlib import Path

from provium import (
    lineage_to_dot,
    lineage_to_mermaid,
    read_artifact_header,
    render_lineage,
)

lineage = read_artifact_header("results.pa").lineage

Path("lineage.dot").write_text(lineage_to_dot(lineage))
Path("lineage.mmd").write_text(
    lineage_to_mermaid(lineage, show_procedure_versions=True)
)
Path("lineage.svg").write_bytes(
    render_lineage(
        lineage,
        format="svg",
        backend="auto",
        show_artifact_identities=True,
    )
)
```

The public signatures are:

```python
lineage_to_dot(
    lineage,
    *,
    show_artifact_identities=False,
    show_procedure_versions=False,
    show_execution_identities=False,
) -> str

lineage_to_mermaid(
    lineage,
    *,
    show_artifact_identities=False,
    show_procedure_versions=False,
    show_execution_identities=False,
) -> str

render_lineage(
    lineage,
    *,
    format: str,
    backend: str = "auto",
    show_artifact_identities=False,
    show_procedure_versions=False,
    show_execution_identities=False,
) -> bytes
```

`format` and `backend` are ordinary strings. Each backend owns format validation;
`render_lineage` raises a backend-specific error for strict selection and a
summary error when no automatic backend can render the requested format.
