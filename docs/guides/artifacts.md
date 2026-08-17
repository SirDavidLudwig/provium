# Artifacts

An artifact combines a payload with metadata describing its identity,
type, integrity, and lineage. Provium supplies `JsonArtifact`; applications can
define their own formats with a reader, writer, and artifact class.

## Define a custom type

```python
import struct

from provium import Artifact, ArtifactReader, ArtifactWriter

INTEGER = struct.Struct(">q")


class IntegerReader(ArtifactReader):
    def read(self) -> int:
        return INTEGER.unpack(self.body.read(INTEGER.size))[0]


class IntegerWriter(ArtifactWriter):
    def write(self, value: int) -> None:
        self.body.write(INTEGER.pack(value))


class IntegerArtifact(Artifact[IntegerReader, IntegerWriter]):
    reader = IntegerReader
    writer = IntegerWriter
```

Typed calls such as `IntegerArtifact.open()` can read these artifacts directly.

## Register a stable identifier

Registration is optional. Register a type when you want a stable identifier,
aliases, or dynamic loading through `provium.open_artifact()`:

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

Without registration, Provium stores the artifact class's full import path as
its identifier.
