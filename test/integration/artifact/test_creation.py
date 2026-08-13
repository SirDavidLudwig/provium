from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from provium import (
    Artifact,
    ArtifactCatalog,
    ArtifactHeader,
    ArtifactReader,
    ArtifactWriter,
    Procedure,
    decode_header,
    open_artifact,
)


class BytesReader(ArtifactReader):
    def read_value(self) -> bytes:
        return self.body.read()


class BytesWriter(ArtifactWriter):
    def write_value(self, value: bytes) -> int:
        return self.body.write(value)


class BytesArtifact(Artifact[BytesReader, BytesWriter]):
    reader = BytesReader
    writer = BytesWriter


@pytest.fixture(autouse=True)
def discovered_catalog(monkeypatch: pytest.MonkeyPatch) -> ArtifactCatalog:
    catalog = ArtifactCatalog()
    catalog.register(
        "example.BytesV1",
        BytesArtifact,
        aliases=("example.LegacyBytesV1",),
    )
    monkeypatch.setattr("provium.procedure.discover_catalogs", lambda: catalog)
    return catalog


def read_body(path: Path) -> tuple[ArtifactHeader, bytes]:
    data = path.read_bytes()
    header = decode_header(data)
    return header, data[header.body_offset : header.body_offset + header.body_length]


def test_creates_empty_output_and_registers_it(tmp_path: Path) -> None:
    path = tmp_path / "empty.pa"

    with Procedure("create", "1").execute() as execution:
        writer = BytesArtifact.create(path)
        assert execution.writers == (writer,)
        assert len(execution.outputs) == 1

    header, body = read_body(path)
    assert body == b""
    assert header.body_length == 0
    assert header.body_digest == hashlib.sha256(b"").hexdigest()
    assert header.artifact_identifier == "example.BytesV1"
    assert header.artifact_identity


def test_streams_body_and_force_finalizes_writer_on_exit(tmp_path: Path) -> None:
    path = tmp_path / "stream.pa"

    with Procedure("create", "1").execute():
        writer = BytesArtifact.create(path)
        writer.write_value(b"abc")
        writer.write_value(b"def")
        assert not writer.closed

    assert writer.closed
    assert writer.container_finalized
    assert read_body(path)[1] == b"abcdef"


def test_seek_and_backpatch_digest_final_actual_bytes(tmp_path: Path) -> None:
    path = tmp_path / "indexed.pa"

    with Procedure("create", "1").execute():
        writer = BytesArtifact.create(path)
        writer.write_value(b"0000payload")
        writer.body.seek(0)
        writer.write_value(b"0011")

    header, body = read_body(path)
    assert body == b"0011payload"
    assert header.body_digest == hashlib.sha256(body).hexdigest()


def test_explicit_close_before_exit_preserves_final_provenance(tmp_path: Path) -> None:
    path = tmp_path / "early.pa"

    with Procedure("create", "1").execute() as execution:
        writer = BytesArtifact.create(path)
        writer.write_value(b"value")
        writer.close()
        assert writer.body_complete
        assert not writer.container_finalized

    header, _ = read_body(path)
    assert writer.container_finalized
    assert header.lineage.executions[execution.identity].procedure.name == "create"


def test_scope_closes_open_readers_and_writers(tmp_path: Path) -> None:
    source = tmp_path / "source.pa"
    with Procedure("seed", "1").execute():
        seed = BytesArtifact.create(source)
        seed.write_value(b"source")

    output = tmp_path / "output.pa"
    with Procedure("copy", "1").execute():
        first = BytesArtifact.open(source)
        second = BytesArtifact.open(source)
        writer = BytesArtifact.create(output)
        writer.write_value(first.read_value())

    assert first.closed
    assert second.closed
    assert writer.closed
    assert writer.container_finalized


def test_multiple_outputs_share_execution_and_complete_io_sets(tmp_path: Path) -> None:
    source = tmp_path / "source.pa"
    with Procedure("seed", "1").execute():
        seed = BytesArtifact.create(source)
        seed.write_value(b"source")

    first_path = tmp_path / "first.pa"
    second_path = tmp_path / "second.pa"
    with Procedure("split", "2").execute() as execution:
        source_reader = open_artifact(source, expected=BytesArtifact)
        first = BytesArtifact.create(first_path)
        first.write_value(source_reader.body.read())
        first.close()
        second = BytesArtifact.create(second_path)
        second.write_value(b"other")

    first_header, _ = read_body(first_path)
    second_header, _ = read_body(second_path)
    first_execution = first_header.lineage.executions[execution.identity]
    second_execution = second_header.lineage.executions[execution.identity]

    assert first_execution == second_execution
    assert {item.identity for item in first_execution.inputs} == {
        source_reader.identity
    }
    assert {item.identity for item in first_execution.outputs} == {
        first.identity,
        second.identity,
    }
    assert first_header.lineage == second_header.lineage


def test_new_provenance_uses_canonical_identifier(tmp_path: Path) -> None:
    path = tmp_path / "canonical.pa"

    with Procedure("create", "1").execute():
        BytesArtifact.create(path)

    header, _ = read_body(path)
    record = header.lineage.artifacts[header.artifact_identity]
    assert record.reference.artifact_identifier == "example.BytesV1"


def test_unregistered_artifact_uses_full_class_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "unregistered.pa"
    monkeypatch.setattr(
        "provium.procedure.discover_catalogs",
        lambda: ArtifactCatalog(),
    )

    with Procedure("create", "1").execute():
        writer = BytesArtifact.create(path)
        writer.write_value(b"value")

    header, body = read_body(path)
    expected = f"{BytesArtifact.__module__}.{BytesArtifact.__qualname__}"
    assert body == b"value"
    assert header.artifact_identifier == expected
    assert header.lineage.artifacts[writer.identity].reference.artifact_identifier == (
        expected
    )


def test_handles_are_invalid_after_exit_and_in_later_context(tmp_path: Path) -> None:
    path = tmp_path / "value.pa"
    with Procedure("create", "1").execute():
        writer = BytesArtifact.create(path)

    with pytest.raises(RuntimeError, match="context"):
        writer.body
    with (
        Procedure("later", "1").execute(),
        pytest.raises(RuntimeError, match="context"),
    ):
        writer.body
