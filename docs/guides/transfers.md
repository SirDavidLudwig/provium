# Dumping and importing artifacts

Portable dump packages preserve an artifact's identity, body digest, and complete
lineage. A package contains `manifest.json` and one body representation:

- A custom `payload/` directory when the artifact's `dump()` and `load()` hooks
  are implemented.
- A lossless `body.dat` fallback otherwise.

Custom packages do not duplicate the body as `body.dat`.

```python
from provium import dump_artifact, import_artifact

dump_artifact("model.pa", "model-dump/")
import_artifact("model-dump/", "restored.pa")
```

The default exact import reconstructs the body and rejects it if its SHA-256 digest
or length differs from the original. Exact imports preserve the original identity
and computational lineage. Dump and import events are appended to the package's
transfer log in `manifest.json`.

## Custom representations

Artifact readers and writers can define a compact or human-editable representation:

```python
class TextArtifact(Artifact[TextReader, TextWriter]):
    reader = TextReader
    writer = TextWriter

    @classmethod
    def dump(cls, reader: TextReader, destination: Path) -> None:
        (destination / "text.txt").write_text(reader.read())

    @classmethod
    def load(cls, source: Path, writer: TextWriter) -> None:
        writer.write((source / "text.txt").read_text())
```

The framework creates the payload directory, hashes every file, validates safe
relative paths, and owns identity and provenance handling.

Use `representation="custom"` to require these hooks or `representation="raw"` to
force `body.dat`. `"auto"` is the default.

## Importing modified content

Changed content is rejected by default. Explicit modes control its provenance:

```python
import_artifact(source, destination, mode="derived")
import_artifact(source, destination, mode="root")
```

- `derived` assigns a new identity and records `provium.import` with the original
  artifact and lineage as its input.
- `root` assigns a new identity, drops inherited lineage, and records a new
  `provium.unsafe-import` provenance root.

Use `inspect_dump()` for package metadata and `verify_dump()` to validate its file
inventory without importing it.

The equivalent commands are:

```console
provium artifact dump model.pa model-dump/
provium artifact import model-dump/ restored.pa
provium artifact inspect-dump model-dump/
provium artifact verify-dump model-dump/
```
