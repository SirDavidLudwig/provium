# Artifacts

An artifact combines a streamed body with a typed identifier, SHA-256 digest,
identity, and complete lineage. Concrete artifact types are classes pairing a
reader and writer.

## Define a custom artifact

```python
import struct
from provium import Artifact, ArtifactDefinition, ArtifactReader, ArtifactWriter

INTEGER = struct.Struct(">q")
INTEGER_DEFINITION = ArtifactDefinition(
    identifier="example.IntegerV1",
    target="your_package.artifacts:IntegerArtifact",
    description="A signed 64-bit integer.",
)


class IntegerReader(ArtifactReader):
    def read(self) -> int:
        return INTEGER.unpack(self.body.read(INTEGER.size))[0]


class IntegerWriter(ArtifactWriter):
    def write(self, value: int) -> int:
        return self.body.write(INTEGER.pack(value))


class IntegerArtifact(Artifact[IntegerReader, IntegerWriter]):
    definition = INTEGER_DEFINITION
    reader = IntegerReader
    writer = IntegerWriter
```

The generic specialization is checked against the declared reader and writer,
so `bind_read().open()` and `bind_write().open()` preserve their concrete types.
Artifacts may additionally define custom `dump` and `load` class methods.

## Register for discovery

```python
from provium import ArtifactCatalog

catalog = ArtifactCatalog()
catalog.register(INTEGER_DEFINITION)
```

Expose the catalog from a plugin distribution:

```toml
[project.entry-points."provium.artifact_catalogs"]
example = "your_package.catalog:catalog"
```

Catalog discovery imports the lightweight catalog module. Calling
`INTEGER_DEFINITION.resolve()` imports and validates the target artifact class.

## Bind paths

Bindings are immutable descriptions; opening performs I/O within an active
session or authorized procedure callback.

```python
from provium import session

source = IntegerArtifact.bind_read("source.pa")
with session():
    with source.open() as reader:
        value = reader.read()
```

Writes are disk-backed from the beginning. Procedure execution stages each body
in a temporary file beside its destination, then writes the variable-length
metadata header and atomically publishes all outputs only after success. Failed
processing leaves existing destinations unchanged.

The fixed header prefix records the metadata and body regions. Metadata length
is determined when an artifact is created, so lineage is not constrained to a
fixed 4096-byte block.
