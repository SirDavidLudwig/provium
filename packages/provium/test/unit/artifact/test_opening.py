"""Tests for opening typed artifact bindings in sessions."""

import hashlib
import io
import struct
from collections.abc import Callable
from pathlib import Path

import pytest

from provium import (
    Artifact,
    ArtifactDefinition,
    ArtifactHeader,
    ArtifactLineage,
    ArtifactReader,
    ArtifactRecord,
    ArtifactReference,
    ArtifactWriter,
    ProcedureExecutionRecord,
    ProcedureRecord,
    encode_header,
    session,
)


class BytesReader(ArtifactReader):
    def read(self) -> bytes:
        return self.body.read()


class BytesWriter(ArtifactWriter):
    pass


BYTES_DEFINITION = ArtifactDefinition(
    identifier="example.BytesV1",
    target=f"{__name__}:BytesArtifact",
    description="Bytes.",
)


class BytesArtifact(Artifact[BytesReader, BytesWriter]):
    definition = BYTES_DEFINITION
    reader = BytesReader
    writer = BytesWriter


class BrokenReader(ArtifactReader):
    def __init__(self, *args: object, **kwargs: object) -> None:
        raise RuntimeError("reader construction failed")


class BrokenArtifact(Artifact[BrokenReader, BytesWriter]):
    definition = ArtifactDefinition(
        identifier="example.BrokenV1",
        target=f"{__name__}:BrokenArtifact",
        description="Broken reader.",
    )
    reader = BrokenReader
    writer = BytesWriter


class InterruptReader(ArtifactReader):
    def __init__(self, *args: object, **kwargs: object) -> None:
        raise KeyboardInterrupt("reader construction interrupted")


class InterruptArtifact(Artifact[InterruptReader, BytesWriter]):
    definition = ArtifactDefinition(
        identifier="example.InterruptV1",
        target=f"{__name__}:InterruptArtifact",
        description="Interrupted reader.",
    )
    reader = InterruptReader
    writer = BytesWriter


def write_artifact(
    path: Path,
    body: bytes = b"body",
    *,
    identity: str = "artifact-1",
    identifier: str = "example.BytesV1",
) -> tuple[ArtifactRecord, ArtifactLineage]:
    reference = ArtifactReference(identity, identifier)
    execution = ProcedureExecutionRecord(
        f"execution-{identity}",
        ProcedureRecord("example.CreateV1", "contract-digest"),
        outputs=(reference,),
    )
    digest = hashlib.sha256(body).hexdigest()
    record = ArtifactRecord(reference, digest, execution.identity)
    lineage = ArtifactLineage.for_execution(execution, (record,))
    header = ArtifactHeader(
        artifact_identifier=identifier,
        artifact_identity=identity,
        body_offset=4096,
        body_length=len(body),
        body_digest=digest,
        lineage=lineage,
    )
    encoded = encode_header(header)
    path.write_bytes(encoded + bytes(header.body_offset - len(encoded)) + body)
    return record, lineage


def test_read_binding_opens_its_concrete_reader_and_tracks_dependency(
    tmp_path: Path,
) -> None:
    path = tmp_path / "value.pa"
    record, lineage = write_artifact(path)
    binding = BytesArtifact.bind_read(path)

    with session() as active:
        reader = binding.open()

        assert isinstance(reader, BytesReader)
        assert reader.read() == b"body"
        assert active.readers == (reader,)
        assert active.inputs == (record,)
        assert active.input_lineage == lineage

    assert reader.closed


def test_read_binding_requires_an_active_session(tmp_path: Path) -> None:
    path = tmp_path / "value.pa"
    write_artifact(path)

    with pytest.raises(RuntimeError, match="active session"):
        BytesArtifact.bind_read(path).open()


def test_session_open_requires_that_exact_session_to_be_active(tmp_path: Path) -> None:
    path = tmp_path / "value.pa"
    write_artifact(path)
    binding = BytesArtifact.bind_read(path)
    inactive = session()

    with pytest.raises(RuntimeError, match="active session"):
        inactive.open_artifact(binding)

    with inactive:
        with session(), pytest.raises(RuntimeError, match="active session"):
            inactive.open_artifact(binding)


def test_typed_open_rejects_a_different_artifact_identifier(tmp_path: Path) -> None:
    path = tmp_path / "other.pa"
    write_artifact(path, identifier="example.OtherV1")

    with session(), pytest.raises(TypeError, match="requested artifact type"):
        BytesArtifact.bind_read(path).open()


def test_open_rejects_a_truncated_or_modified_body(tmp_path: Path) -> None:
    path = tmp_path / "value.pa"
    write_artifact(path)
    complete = path.read_bytes()

    path.write_bytes(complete[:-1])
    with session(), pytest.raises(ValueError, match="truncated"):
        BytesArtifact.bind_read(path).open()

    modified = bytearray(complete)
    modified[-1] ^= 1
    path.write_bytes(modified)
    with session(), pytest.raises(ValueError, match="digest"):
        BytesArtifact.bind_read(path).open()


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda data: data[:10], "fixed header"),
        (lambda data: b"BADMAGIC" + data[8:], "magic"),
        (
            lambda data: data[:8] + struct.pack(">H", 2) + data[10:],
            "version",
        ),
    ],
)
def test_open_rejects_an_invalid_fixed_header(
    tmp_path: Path,
    mutation: Callable[[bytes], bytes],
    message: str,
) -> None:
    path = tmp_path / "invalid.pa"
    write_artifact(path)
    path.write_bytes(mutation(path.read_bytes()))

    with session(), pytest.raises(ValueError, match=message):
        BytesArtifact.bind_read(path).open()


def test_opening_the_same_artifact_tracks_one_input_and_each_reader(
    tmp_path: Path,
) -> None:
    path = tmp_path / "value.pa"
    record, _ = write_artifact(path)

    with session() as active:
        first = BytesArtifact.bind_read(path).open()
        second = BytesArtifact.bind_read(path).open()

        assert active.inputs == (record,)
        assert active.readers == (first, second)


def test_reader_construction_failure_closes_the_artifact_stream(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "broken.pa"
    write_artifact(path, identifier="example.BrokenV1")
    stream = io.BytesIO(path.read_bytes())
    monkeypatch.setattr(Path, "open", lambda *_args, **_kwargs: stream)

    with session(), pytest.raises(RuntimeError, match="construction failed"):
        BrokenArtifact.bind_read(path).open()

    assert stream.closed


def test_interrupted_reader_construction_closes_the_artifact_stream(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "interrupted.pa"
    write_artifact(path, identifier="example.InterruptV1")
    stream = io.BytesIO(path.read_bytes())
    monkeypatch.setattr(Path, "open", lambda *_args, **_kwargs: stream)

    with session(), pytest.raises(KeyboardInterrupt, match="interrupted"):
        InterruptArtifact.bind_read(path).open()

    assert stream.closed


def test_conflicting_lineage_does_not_register_a_partial_reader(
    tmp_path: Path,
) -> None:
    first_path = tmp_path / "first.pa"
    second_path = tmp_path / "second.pa"
    first_record, _ = write_artifact(first_path, b"first")
    write_artifact(second_path, b"second")

    with session() as active:
        first = BytesArtifact.bind_read(first_path).open()
        with pytest.raises(ValueError, match="artifact conflict"):
            BytesArtifact.bind_read(second_path).open()

        assert active.inputs == (first_record,)
        assert active.readers == (first,)


def test_checksum_streaming_detects_an_unexpected_end_of_file() -> None:
    class EmptyThenFail(io.BytesIO):
        def read(self, size: int = -1) -> bytes:
            if self.tell() == 0:
                self.seek(1)
                return b""
            raise AssertionError("checksum reader retried after end of file")

    with pytest.raises(ValueError, match="truncated"):
        session()._verify_digest(
            EmptyThenFail(),
            0,
            1,
            hashlib.sha256(b"x").hexdigest(),
        )


def test_nested_sessions_inherit_ancestor_dependencies(tmp_path: Path) -> None:
    parent_path = tmp_path / "parent.pa"
    child_path = tmp_path / "child.pa"
    parent_record, parent_lineage = write_artifact(
        parent_path,
        identity="parent-artifact",
    )
    child_record, child_lineage = write_artifact(
        child_path,
        identity="child-artifact",
    )

    with session():
        BytesArtifact.bind_read(parent_path).open()
        with session() as child:
            BytesArtifact.bind_read(child_path).open()

            assert child.inputs == (parent_record, child_record)
            assert child.input_lineage == parent_lineage.merge(child_lineage)
