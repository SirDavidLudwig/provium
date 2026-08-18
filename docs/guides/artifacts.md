# Artifacts

An artifact combines a payload with metadata describing its identity,
type, integrity, and lineage. Provium supplies `JsonArtifact`; applications can
define their own formats with reader and writer classes plus an artifact definition.

## Define a custom type

```python
import struct

from provium import Artifact, ArtifactReader, ArtifactWriter

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
    label="Integer",
    reader=IntegerReader,
    writer=IntegerWriter,
)
```

Typed calls such as `IntegerArtifact.open()` can read these artifacts directly.
The optional `inspect()` method supplies body details for `provium inspect
--body`. Its return value is rendered as JSON when possible, with unsupported
objects represented using `repr()`.

## Register a stable identifier

Registration is optional. Register a type when you want a stable identifier or
dynamic loading through `provium.open_artifact()`:

```python
from provium import ArtifactCatalog

from .artifacts import IntegerArtifact

catalog = ArtifactCatalog()
catalog.register("example.IntegerV1", IntegerArtifact)
```

Expose the catalog through a package entry point:

```toml
[project.entry-points."provium.catalogs"]
example = "your_package.catalog:catalog"
```

Without registration, Provium derives an identifier from the reader module and
artifact label. Set `identifier=` on the definition or register it when the
identifier must remain stable across refactors.

## Bind a path

Artifact definitions can be bound to a read or write path and opened later:

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
