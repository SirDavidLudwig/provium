# Provium

Provium helps you build processing workflows whose results explain where they
came from. Store a result as an artifact, use that artifact as input to another
step, and save the new outputs as artifacts of their own. Provium records those
relationships automatically as your workflow runs.

Each processing step is represented by a versioned procedure. When a procedure
reads existing artifacts and creates new ones, Provium links the outputs to the
procedure and its inputs. That lineage travels with every result, including its
full upstream history, so a final artifact can be traced back through every
intermediate result and the procedures that produced them.

This keeps provenance out of your application logic: you work with inputs,
perform the computation, and write outputs inside a procedure execution. Provium
handles the dependency graph, integrity metadata, and lifecycle of those
artifacts for you.

## Features

- Typed readers and writers for application-specific binary formats
- Automatic input, output, and procedure lineage
- SHA-256 payload integrity checks
- Streaming, body-relative binary I/O
- Runtime artifact discovery through Python entry points
- Optional configuration snapshots, including Pydantic v2 models
- No required runtime dependencies

## Installation

Provium requires Python 3.12 or newer.

```bash
python -m pip install provium
```

## Quick start

Define an artifact that stores a signed 64-bit integer:

```python
import struct

from provium import Artifact, ArtifactReader, ArtifactWriter

INTEGER = struct.Struct(">q")


class IntegerReader(ArtifactReader):
    def read_value(self) -> int:
        return INTEGER.unpack(self.body.read(INTEGER.size))[0]


class IntegerWriter(ArtifactWriter):
    def write_value(self, value: int) -> None:
        self.body.write(INTEGER.pack(value))


class IntegerArtifact(Artifact[IntegerReader, IntegerWriter]):
    reader = IntegerReader
    writer = IntegerWriter
```

Create and consume artifacts inside procedure executions:

```python
from provium import Procedure

from your_package.artifacts import IntegerArtifact

SOURCE = Procedure(name="source", version="1")
ADD = Procedure(name="add", version="1")

with SOURCE.execute():
    left = IntegerArtifact.create("left.pa")
    left.write_value(2)

    right = IntegerArtifact.create("right.pa")
    right.write_value(3)

with ADD.execute():
    left = IntegerArtifact.open("left.pa")
    right = IntegerArtifact.open("right.pa")
    total = IntegerArtifact.create("sum.pa")
    total.write_value(left.read_value() + right.read_value())
```

Registration is optional. Without it, Provium stores the artifact class's full
path, such as `your_package.artifacts.IntegerArtifact`, as its identifier. Typed
calls such as `IntegerArtifact.open()` can read these artifacts directly.

Register the artifact when you want a stable custom identifier, aliases, or
dynamic loading through `provium.open_artifact()`:

```python
from provium import ArtifactCatalog

from .artifacts import IntegerArtifact

catalog = ArtifactCatalog()
catalog.register("example.IntegerV1", IntegerArtifact)
```

Expose that catalog from `pyproject.toml` so Provium can discover it:

```toml
[project.entry-points."provium.catalogs"]
example = "your_package.catalog:catalog"
```

When each context exits successfully, Provium closes its handles and finalizes
its output files. `sum.pa` contains the value `5` and records the `add` execution,
both of its integer inputs, and their producing execution. If a context exits
with an exception, its pending outputs are not committed.

Readers and writers are bound to the execution that created them and cannot be
used after that context exits. Nested execution contexts are also rejected.

## Inspecting provenance

Every reader exposes the artifact header and lineage:

```python
from provium import Procedure

from your_package.artifacts import IntegerArtifact

with Procedure("inspect", "1").execute():
    artifact = IntegerArtifact.open("sum.pa")
    print(artifact.read_value())
    print(artifact.identity)
    print(artifact.artifact_identifier)
    print(artifact.lineage.to_json())
```

Use `provium.open_artifact()` when the concrete type should be resolved from the
identifier stored in the file rather than selected in advance.

## Command-line tools

Inspect an artifact's generic metadata without loading its concrete artifact
type:

```bash
provium inspect result.pa
```

Generate Mermaid or Graphviz source for an artifact's complete lineage:

```bash
provium graph --renderer mermaid result.pa lineage.mmd
provium graph --renderer graphviz result.pa lineage.dot
```

Image output supports SVG, PNG, and PDF and defaults to the Mermaid renderer:

```bash
provium graph result.pa lineage.svg
provium graph --renderer graphviz result.pa lineage.png
```

Mermaid image rendering requires the official `mmdc` executable. Graphviz
rendering requires the optional Python package and Graphviz system package:

```bash
npm install --global @mermaid-js/mermaid-cli
python -m pip install 'provium[visualization]'
```

The output type is inferred from its extension. Library callers can use the
functions in `provium.tool` to produce Mermaid or DOT source and to receive
rendered images as bytes.

## Development

Create a virtual environment and install the project with its test dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[test]'
```

Run the test suite:

```bash
pytest
```

This also runs Ruff linting and `ruff format --check` over `src` and `test`.
The project requires 100% statement and branch coverage for the `provium`
package.
