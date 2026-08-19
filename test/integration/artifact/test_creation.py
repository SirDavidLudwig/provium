from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from provium import (
    Artifact,
    ArtifactCatalog,
    ArtifactDefinition,
    ArtifactHeader,
    ArtifactReader,
    ArtifactWriter,
    Procedure,
    decode_header,
    open_artifact,
)


class BytesReader(ArtifactReader):
    def read(self) -> bytes:
        return self.body.read()


class BytesWriter(ArtifactWriter):
    def write(self, value: bytes) -> int:
        return self.body.write(value)


BytesArtifact = Artifact("example.BytesV1", "Bytes", BytesReader, BytesWriter)


@pytest.fixture(autouse=True)
def discovered_catalog(monkeypatch: pytest.MonkeyPatch) -> ArtifactCatalog:
    catalog = ArtifactCatalog()
    catalog.register(
        ArtifactDefinition("example.BytesV1", f"{__name__}:BytesArtifact", "Bytes.")
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
        writer.write(b"abc")
        writer.write(b"def")
        assert not writer.closed

    assert writer.closed
    assert writer.container_finalized
    assert read_body(path)[1] == b"abcdef"


def test_streams_body_through_a_temporary_disk_file(tmp_path: Path) -> None:
    path = tmp_path / "large.pa"
    body = b"x" * (2 * 1024 * 1024)

    with Procedure("create", "1").execute() as execution:
        writer = BytesArtifact.create(path)
        writer.write(body)
        pending = execution._pending_outputs[0]
        assert not path.exists()
        assert pending.temporary_path.exists()
        assert (
            pending.temporary_path.stat().st_size
            == writer.metadata.body_offset + len(body)
        )

    assert path.stat().st_size == writer.metadata.body_offset + len(body)
    assert not pending.temporary_path.exists()


def test_seek_and_backpatch_digest_final_actual_bytes(tmp_path: Path) -> None:
    path = tmp_path / "indexed.pa"

    with Procedure("create", "1").execute():
        writer = BytesArtifact.create(path)
        writer.write(b"0000payload")
        writer.body.seek(0)
        writer.write(b"0011")

    header, body = read_body(path)
    assert body == b"0011payload"
    assert header.body_digest == hashlib.sha256(body).hexdigest()


def test_explicit_close_before_exit_preserves_final_provenance(tmp_path: Path) -> None:
    path = tmp_path / "early.pa"

    with Procedure("create", "1").execute() as execution:
        writer = BytesArtifact.create(path)
        writer.write(b"value")
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
        seed.write(b"source")

    output = tmp_path / "output.pa"
    with Procedure("copy", "1").execute():
        first = BytesArtifact.open(source)
        second = BytesArtifact.open(source)
        writer = BytesArtifact.create(output)
        writer.write(first.read())

    assert first.closed
    assert second.closed
    assert writer.closed
    assert writer.container_finalized


def test_multiple_outputs_share_execution_and_complete_io_sets(tmp_path: Path) -> None:
    source = tmp_path / "source.pa"
    with Procedure("seed", "1").execute():
        seed = BytesArtifact.create(source)
        seed.write(b"source")

    first_path = tmp_path / "first.pa"
    second_path = tmp_path / "second.pa"
    with Procedure("split", "2").execute() as execution:
        source_reader = open_artifact(source, expected=BytesArtifact)
        first = BytesArtifact.create(first_path)
        first.write(source_reader.body.read())
        first.close()
        second = BytesArtifact.create(second_path)
        second.write(b"other")

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


def test_rejects_duplicate_output_destinations_in_one_execution(
    tmp_path: Path,
) -> None:
    path = tmp_path / "duplicate.pa"

    with Procedure("duplicate", "1").execute() as execution:
        first = BytesArtifact.create(path)
        first.write(b"first")
        with pytest.raises(ValueError, match="destination"):
            BytesArtifact.create(path)
        assert execution.writers == (first,)

    assert read_body(path)[1] == b"first"
    assert not list(tmp_path.glob(".*.tmp"))


def test_new_provenance_uses_canonical_identifier(tmp_path: Path) -> None:
    path = tmp_path / "canonical.pa"

    with Procedure("create", "1").execute():
        BytesArtifact.create(path)

    header, _ = read_body(path)
    record = header.lineage.artifacts[header.artifact_identity]
    assert record.reference.artifact_identifier == "example.BytesV1"


def test_imperative_artifact_uses_its_required_identifier(
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
        writer.write(b"value")

    header, body = read_body(path)
    expected = BytesArtifact.identifier
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
