# Dumping and loading artifacts

Portable dump packages preserve an artifact's identity, body digest, and complete
lineage. A package contains `manifest.json` and one body representation:

- A custom `payload/` directory when the artifact's `dump()` and `load()` hooks
  are implemented.
- A lossless `body.dat` fallback otherwise.

Custom packages do not duplicate the body as `body.dat`.

```python
from provium import dump_artifact, load_artifact

dump_artifact("model.pa", "model-dump/")
load_artifact("model-dump/", "restored.pa")
```

The default exact load reconstructs the body and rejects it if its SHA-256 digest
or length differs from the original. Exact imports preserve the original identity
and computational lineage. Dump and load events are appended to the package's
transfer log in `manifest.json`.

## Custom representations

Artifact definitions can provide a compact or human-editable representation:

```python
def dump_text(reader: TextReader, destination: Path) -> None:
    (destination / "text.txt").write_text(reader.read())


def load_text(source: Path, writer: TextWriter) -> None:
    writer.write((source / "text.txt").read_text())


TextArtifact = Artifact(
    identifier="example.TextV1",
    label="Text",
    reader=TextReader,
    writer=TextWriter,
    dump=dump_text,
    load=load_text,
)
```

The framework creates the payload directory, hashes every file, validates safe
relative paths, and owns identity and provenance handling.

Use `representation="custom"` to require these hooks or `representation="raw"` to
force `body.dat`. `"auto"` is the default.

## Loading modified content

Changed content is rejected by default. Explicit modes control its provenance:

```python
load_artifact(source, destination, mode="derived")
load_artifact(source, destination, mode="root")
```

- `derived` assigns a new identity and records `provium.load` with the original
  artifact and lineage as its input.
- `root` assigns a new identity, drops inherited lineage, and records a new
  `provium.unsafe-load` provenance root.

Use `inspect_dump()` for package metadata and `verify_dump()` to validate its file
inventory without loading it.

The equivalent commands are:

```console
provium artifact dump model.pa model-dump/
provium artifact load model-dump/ restored.pa
provium artifact inspect-dump model-dump/
provium artifact verify-dump model-dump/
```
