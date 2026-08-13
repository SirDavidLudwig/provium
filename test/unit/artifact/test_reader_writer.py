from __future__ import annotations

import io
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass

import pytest

from provium import (
    ArtifactHeader,
    ArtifactLineage,
    ArtifactReader,
    ArtifactRecord,
    ArtifactReference,
    ArtifactWriter,
    ProcedureExecutionRecord,
    ProcedureRecord,
)
from provium.artifact.region import BodyRegion
from provium.context import activate_context


@dataclass
class Owner:
    active: bool = True


@contextmanager
def active(owner: Owner) -> Generator[None]:
    with activate_context(owner):
        yield


def artifact_header() -> ArtifactHeader:
    reference = ArtifactReference("artifact-1", "example.BytesV1")
    execution = ProcedureExecutionRecord(
        "execution-1",
        ProcedureRecord("create", "1"),
        outputs=(reference,),
    )
    lineage = ArtifactLineage.for_execution(
        execution,
        (ArtifactRecord(reference, "digest", execution.identity),),
    )
    return ArtifactHeader(
        artifact_identifier=reference.artifact_identifier,
        artifact_identity=reference.identity,
        body_offset=100,
        body_length=4,
        body_digest="digest",
        lineage=lineage,
    )


class BytesReader(ArtifactReader):
    def read(self) -> bytes:
        return self.body.read()


class BytesWriter(ArtifactWriter):
    def write(self, value: bytes) -> int:
        return self.body.write(value)


def make_reader() -> tuple[BytesReader, Owner]:
    owner = Owner()
    stream = io.BytesIO(bytes(100) + b"data")
    region = BodyRegion(stream, 100, 4, owner)
    return BytesReader(region, artifact_header()), owner


def make_writer(
    *, finalizer: object | None = None
) -> tuple[BytesWriter, Owner, io.BytesIO]:
    owner = Owner()
    stream = io.BytesIO(bytes(100))
    region = BodyRegion(stream, 100, 0, owner, writable=True)
    return BytesWriter(region, artifact_header(), finalizer=finalizer), owner, stream


def test_reader_exposes_metadata_identity_lineage_and_bounded_body() -> None:
    reader, owner = make_reader()

    with active(owner):
        assert reader.metadata == artifact_header()
        assert reader.identity == "artifact-1"
        assert reader.artifact_identifier == "example.BytesV1"
        assert reader.lineage == artifact_header().lineage
        assert reader.read() == b"data"


def test_reader_closes_explicitly_and_idempotently() -> None:
    reader, owner = make_reader()

    with active(owner):
        reader.close()
        reader.close()
        assert reader.closed
        with pytest.raises(ValueError, match="closed"):
            reader.read()


def test_reader_context_manager_closes_on_exit() -> None:
    reader, owner = make_reader()

    with active(owner), reader as entered:
        assert entered is reader

    assert reader.closed


def test_reader_rejects_another_or_ended_context() -> None:
    reader, owner = make_reader()

    with active(Owner()), pytest.raises(RuntimeError, match="context"):
        reader.read()
    owner.active = False
    with active(owner), pytest.raises(RuntimeError, match="active"):
        reader.read()


def test_writer_exposes_writable_body_with_streaming_and_backpatching() -> None:
    writer, owner, stream = make_writer()

    with active(owner):
        assert writer.metadata == artifact_header()
        assert writer.identity == "artifact-1"
        assert writer.artifact_identifier == "example.BytesV1"
        assert writer.lineage == artifact_header().lineage
        writer.write(b"0000payload")
        writer.body.seek(0)
        writer.write(b"0011")

    assert stream.getvalue()[100:] == b"0011payload"


def test_writer_close_completes_body_but_does_not_finalize_container() -> None:
    calls: list[BytesWriter] = []
    writer, owner, _ = make_writer(finalizer=calls.append)

    with active(owner):
        writer.write(b"data")
        writer.close()
        writer.close()

    assert writer.closed
    assert writer.body_complete
    assert not writer.container_finalized
    assert calls == []


def test_writer_finalization_is_separate_and_idempotent() -> None:
    calls: list[BytesWriter] = []
    writer, owner, _ = make_writer(finalizer=calls.append)

    with active(owner):
        writer.write(b"data")
        writer.finalize()
        writer.finalize()

    assert writer.closed
    assert writer.body_complete
    assert writer.container_finalized
    assert calls == [writer]


def test_writer_context_manager_only_completes_body() -> None:
    writer, owner, _ = make_writer()

    with active(owner), writer as entered:
        assert entered is writer
        entered.write(b"data")

    assert writer.body_complete
    assert not writer.container_finalized


def test_writer_rejects_operations_after_close() -> None:
    writer, owner, _ = make_writer()

    with active(owner):
        writer.close()
        with pytest.raises(ValueError, match="closed"):
            writer.write(b"data")
        with pytest.raises(ValueError, match="closed"):
            writer.body


def test_writer_rejects_another_or_ended_context() -> None:
    writer, owner, _ = make_writer()

    with active(Owner()), pytest.raises(RuntimeError, match="context"):
        writer.write(b"data")
    owner.active = False
    with active(owner), pytest.raises(RuntimeError, match="active"):
        writer.write(b"data")


def test_finalize_requires_active_owner_and_cannot_run_twice_after_close() -> None:
    writer, owner, _ = make_writer()

    with active(owner):
        writer.close()
        writer.finalize()
    assert writer.container_finalized

    with active(owner):
        writer.finalize()


def test_base_constructors_validate_arguments() -> None:
    owner = Owner()
    region = BodyRegion(io.BytesIO(), 0, 0, owner)

    with pytest.raises(TypeError, match="BodyRegion"):
        BytesReader(object(), artifact_header())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="metadata"):
        BytesReader(region, object())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="BodyRegion"):
        BytesWriter(object(), artifact_header())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="metadata"):
        BytesWriter(region, object())  # type: ignore[arg-type]
