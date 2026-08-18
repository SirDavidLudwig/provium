# Artifacts

An artifact combines a payload with metadata describing its identity,
type, integrity, and lineage. Provium supplies `JsonArtifact`; applications can
define their own formats with reader and writer classes plus an artifact instance.

## Define a custom type

```python
import struct

from provium import Artifact, ArtifactReader, ArtifactWriter

from .definitions import INTEGER_ARTIFACT

INTEGER = struct.Struct(">q")


class IntegerReader(ArtifactReader):
    def read(self) -> int:
        return INTEGER.unpack(self.body.read(INTEGER.size))[0]

    def inspect(self) -> object:
        return {"value": self.read()}


class IntegerWriter(ArtifactWriter):
    def write(self, value: int) -> None:
        self.body.write(INTEGER.pack(value))


IntegerArtifact = Artifact(
    identifier=INTEGER_ARTIFACT.identifier,
    label="Integer",
    reader=IntegerReader,
    writer=IntegerWriter,
)
```

Typed calls such as `IntegerArtifact.open()` can read these artifacts directly.
The optional `inspect()` method supplies body details for `provium inspect
--body`. Its return value is rendered as JSON when possible, with unsupported
objects represented using `repr()`.

## Register for dynamic discovery

Every artifact requires a persistent identifier. A catalog definition makes that
identifier dynamically discoverable without importing the implementation:

```python
from provium import ArtifactCatalog, ArtifactDefinition

INTEGER_ARTIFACT = ArtifactDefinition(
    identifier="example.IntegerV1",
    target="your_package.artifacts:IntegerArtifact",
    description="A signed 64-bit integer.",
)

catalog = ArtifactCatalog()
catalog.register(INTEGER_ARTIFACT)
```

Expose the catalog through a package entry point:

```toml
[project.entry-points."provium.catalogs"]
example = "your_package.catalog:catalog"
```

Keeping the definition in a small `definitions` module lets the implementation
reuse its identifier without duplicating the string. Catalog discovery imports
that definition module only. The target module is loaded when Provium encounters
`example.IntegerV1`. Resolution verifies that the target is an `Artifact` with
the same identifier. Imperative use does not require registration because
`IntegerArtifact` carries its identifier directly.

## Bind a path

Artifact instances can be bound to a read or write path and opened later:

```python
source = IntegerArtifact.bind_read("source.pa")
destination = IntegerArtifact.bind_write("result.pa")

with source.open() as reader:
    value = reader.read()

with destination.open() as writer:
    writer.write(value)
```

Artifact I/O accepts explicit filesystem paths only. Output bodies stream through
a temporary file beside the destination; successful procedure finalization writes
the checksum and lineage header and atomically replaces the destination.
