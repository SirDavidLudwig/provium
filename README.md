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

Define reader, writer, and artifact classes for your binary format:

```python
from provium import Artifact, ArtifactReader, ArtifactWriter


class BytesReader(ArtifactReader):
    def read_value(self) -> bytes:
        return self.body.read()


class BytesWriter(ArtifactWriter):
    def write_value(self, value: bytes) -> int:
        return self.body.write(value)


class BytesArtifact(Artifact[BytesReader, BytesWriter]):
    reader = BytesReader
    writer = BytesWriter
```

Publish the artifact through a catalog in your package:

```python
from provium import ArtifactCatalog

from .artifacts import BytesArtifact

catalog = ArtifactCatalog()
catalog.register("example.BytesV1", BytesArtifact)
```

Then expose that catalog from `pyproject.toml`. The identifier is stored in each
artifact, so keep it stable once files have been created.

```toml
[project.entry-points."provium.catalogs"]
example = "your_package.catalog:catalog"
```

You can now create and consume artifacts inside procedure executions:

```python
from provium import Procedure

from your_package.artifacts import BytesArtifact

SOURCE = Procedure(name="source", version="1")
COPY = Procedure(name="copy", version="1")

with SOURCE.execute():
    output = BytesArtifact.create("source.pa")
    output.write_value(b"hello")

with COPY.execute():
    source = BytesArtifact.open("source.pa")
    copy = BytesArtifact.create("copy.pa")
    copy.write_value(source.read_value())
```

When each context exits successfully, Provium closes its handles and finalizes
its output files. `copy.pa` records both procedure executions and the relationship
between the source and copied artifacts. If a context exits with an exception,
its pending outputs are not committed.

Readers and writers are bound to the execution that created them and cannot be
used after that context exits. Nested execution contexts are also rejected.

## Inspecting provenance

Every reader exposes the artifact header and lineage:

```python
from provium import Procedure

from your_package.artifacts import BytesArtifact

with Procedure("inspect", "1").execute():
    artifact = BytesArtifact.open("copy.pa")
    print(artifact.identity)
    print(artifact.artifact_identifier)
    print(artifact.lineage.to_json())
```

Use `provium.open_artifact()` when the concrete type should be resolved from the
identifier stored in the file rather than selected in advance.

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

The project requires 100% statement and branch coverage for the `provium`
package.
