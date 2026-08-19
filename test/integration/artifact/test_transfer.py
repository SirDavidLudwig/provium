from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from provium import (
    Artifact,
    ArtifactCatalog,
    ArtifactDefinition,
    ArtifactReader,
    ArtifactWriter,
    Procedure,
    decode_header,
    dump_artifact,
    inspect_dump,
    load_artifact,
    verify_dump,
)


class TextReader(ArtifactReader):
    def read(self) -> str:
        return self.body.read().decode()


class TextWriter(ArtifactWriter):
    def write(self, value: str) -> None:
        self.body.write(value.encode())


def dump_text(reader: TextReader, destination: Path) -> None:
    (destination / "text.txt").write_text(reader.read())


def load_text(source: Path, writer: TextWriter) -> None:
    writer.write((source / "text.txt").read_text())


TextArtifact = Artifact(
    "example.TextV1",
    "Text",
    reader=TextReader,
    writer=TextWriter,
    dump=dump_text,
    load=load_text,
)


class BytesReader(ArtifactReader):
    def read(self) -> bytes:
        return self.body.read()


class BytesWriter(ArtifactWriter):
    def write(self, value: bytes) -> None:
        self.body.write(value)


BytesArtifact = Artifact("example.BytesV1", "Bytes", BytesReader, BytesWriter)


@pytest.fixture(autouse=True)
def catalog(monkeypatch: pytest.MonkeyPatch) -> ArtifactCatalog:
    value = ArtifactCatalog()
    value.register(
        ArtifactDefinition("example.TextV1", f"{__name__}:TextArtifact", "Text.")
    )
    value.register(
        ArtifactDefinition("example.BytesV1", f"{__name__}:BytesArtifact", "Bytes.")
    )
    monkeypatch.setattr("provium.artifact.transfer.discover_catalogs", lambda: value)
    monkeypatch.setattr("provium.procedure.discover_catalogs", lambda: value)
    return value


def create(path: Path, artifact: Artifact, value: object) -> None:
    with Procedure("create", "1").execute():
        writer = artifact.create(path)
        writer.write(value)  # type: ignore[attr-defined]


def test_custom_dump_and_exact_import_preserve_artifact(tmp_path: Path) -> None:
    source = tmp_path / "source.pa"
    package = tmp_path / "dump"
    restored = tmp_path / "restored.pa"
    create(source, TextArtifact, "hello")

    dumped = dump_artifact(source, package)
    assert dumped.representation == "custom"
    assert (package / "payload" / "text.txt").read_text() == "hello"
    assert not (package / "body.dat").exists()

    loaded = load_artifact(package, restored)
    assert loaded.integrity == "exact"
    assert loaded.identity_preserved
    assert restored.read_bytes() == source.read_bytes()
    assert [event["kind"] for event in inspect_dump(package).events] == [
        "dump",
        "load",
    ]


def test_raw_fallback_and_forced_modes(tmp_path: Path) -> None:
    source = tmp_path / "source.pa"
    package = tmp_path / "dump"
    create(source, BytesArtifact, b"hello")

    result = dump_artifact(source, package)
    assert result.representation == "raw"
    assert (package / "body.dat").read_bytes() == b"hello"
    assert verify_dump(package).valid

    with pytest.raises(ValueError, match="not custom"):
        load_artifact(
            package,
            tmp_path / "wrong.pa",
            representation="custom",
        )

    with pytest.raises(ValueError, match="custom dump"):
        dump_artifact(source, tmp_path / "custom", representation="custom")


def test_modified_custom_import_requires_policy(tmp_path: Path) -> None:
    source = tmp_path / "source.pa"
    package = tmp_path / "dump"
    create(source, TextArtifact, "before")
    original = decode_header(source.read_bytes())
    dump_artifact(source, package)
    payload = package / "payload" / "text.txt"
    payload.write_text("after")
    manifest = json.loads((package / "manifest.json").read_text())
    manifest["representation"]["files"][0]["size"] = len(b"after")
    manifest["representation"]["files"][0]["digest"] = hashlib.sha256(
        b"after"
    ).hexdigest()
    (package / "manifest.json").write_text(json.dumps(manifest))

    with pytest.raises(ValueError, match="differs"):
        load_artifact(package, tmp_path / "rejected.pa")

    derived_path = tmp_path / "derived.pa"
    derived = load_artifact(package, derived_path, mode="derived")
    derived_header = decode_header(derived_path.read_bytes())
    assert derived.integrity == "modified"
    assert not derived.identity_preserved
    assert derived_header.artifact_identity != original.artifact_identity
    assert any(
        execution.procedure.name == "provium.load"
        for execution in derived_header.lineage.executions.values()
    )

    root_path = tmp_path / "root.pa"
    load_artifact(package, root_path, mode="root")
    root_header = decode_header(root_path.read_bytes())
    assert len(root_header.lineage.artifacts) == 1
    assert (
        root_header.lineage.producing_execution(
            next(iter(root_header.lineage.artifacts.values())).reference
        ).procedure.name
        == "provium.unsafe-load"
    )


def test_dump_verification_detects_changes_and_destination_rules(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.pa"
    package = tmp_path / "dump"
    create(source, BytesArtifact, b"hello")
    dump_artifact(source, package)

    with pytest.raises(FileExistsError):
        dump_artifact(source, package)
    (package / "body.dat").write_bytes(b"changed")
    result = verify_dump(package)
    assert not result.valid
    assert result.errors
    with pytest.raises(ValueError, match="verification"):
        load_artifact(package, tmp_path / "bad.pa")
