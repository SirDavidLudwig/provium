"""Tests for typed artifact writers."""

import io
from dataclasses import dataclass

import pytest

from provium import (
    ArtifactHeader,
    ArtifactLineage,
    ArtifactRecord,
    ArtifactReference,
    ArtifactWriter,
    BodyRegion,
    ProcedureExecutionRecord,
    ProcedureRecord,
)
from provium.context import activate_context


@dataclass
class Owner:
    active: bool = True


def header(
    *,
    artifact_identity: str = "artifact-1",
    artifact_identifier: str = "example.BytesV1",
    body_offset: int = 4096,
    body_length: int = 0,
    body_digest: str = "a" * 64,
) -> ArtifactHeader:
    reference = ArtifactReference(artifact_identity, artifact_identifier)
    execution = ProcedureExecutionRecord(
        "execution-1",
        ProcedureRecord("example.CreateV1", "contract-digest"),
        outputs=(reference,),
    )
    lineage = ArtifactLineage.for_execution(
        execution,
        (ArtifactRecord(reference, body_digest, execution.identity),),
    )
    return ArtifactHeader(
        artifact_identifier=reference.artifact_identifier,
        artifact_identity=reference.identity,
        body_offset=body_offset,
        body_length=body_length,
        body_digest=body_digest,
        lineage=lineage,
    )


def writer(
    owner: Owner,
    stream: io.BytesIO,
    *,
    finalizer: object = None,
) -> ArtifactWriter:
    body = BodyRegion(stream, 4096, 0, owner, writable=True)
    return ArtifactWriter(body, header(), finalizer=finalizer)  # type: ignore[arg-type]


def test_writer_exposes_provisional_metadata_and_disk_backed_body() -> None:
    owner = Owner()
    stream = io.BytesIO()
    artifact_writer = writer(owner, stream)

    assert artifact_writer.identity == "artifact-1"
    assert artifact_writer.artifact_identifier == "example.BytesV1"
    assert artifact_writer.lineage is artifact_writer.metadata.lineage
    assert not artifact_writer.closed
    assert not artifact_writer.body_complete
    assert not artifact_writer.container_finalized

    with activate_context(owner):
        assert artifact_writer.body.write(b"body") == 4
        artifact_writer.body.flush()

    assert stream.getvalue()[4096:] == b"body"


def test_writer_context_manager_closes_only_the_body() -> None:
    owner = Owner()
    artifact_writer = writer(owner, io.BytesIO())

    with activate_context(owner):
        with artifact_writer as entered:
            assert entered is artifact_writer
            entered.body.write(b"body")
        assert artifact_writer.closed
        assert artifact_writer.body_complete
        assert not artifact_writer.container_finalized
        artifact_writer.close()


def test_writer_can_finalize_without_a_callback() -> None:
    owner = Owner()
    artifact_writer = writer(owner, io.BytesIO())

    with activate_context(owner):
        artifact_writer.finalize()

    assert artifact_writer.container_finalized


def test_writer_does_not_finalize_with_stale_provisional_metadata() -> None:
    owner = Owner()
    artifact_writer = writer(owner, io.BytesIO())

    with activate_context(owner):
        artifact_writer.body.write(b"body")
        with pytest.raises(ValueError, match="body length"):
            artifact_writer.finalize()

    assert artifact_writer.closed
    assert not artifact_writer.container_finalized


def test_finalize_closes_body_runs_finalizer_once_and_replaces_metadata() -> None:
    owner = Owner()
    calls: list[ArtifactWriter] = []
    final_metadata = header(body_length=4, body_digest="b" * 64)

    def finalize(artifact_writer: ArtifactWriter) -> None:
        assert artifact_writer.closed
        calls.append(artifact_writer)
        artifact_writer._replace_metadata(final_metadata)

    artifact_writer = writer(owner, io.BytesIO(), finalizer=finalize)

    with activate_context(owner):
        artifact_writer.body.write(b"body")
        artifact_writer.finalize()
        artifact_writer.finalize()

    assert calls == [artifact_writer]
    assert artifact_writer.metadata is final_metadata
    assert artifact_writer.container_finalized


def test_failed_finalization_can_be_retried() -> None:
    owner = Owner()
    attempts = 0

    def finalize(_: ArtifactWriter) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("finalization failed")

    artifact_writer = writer(owner, io.BytesIO(), finalizer=finalize)

    with activate_context(owner):
        with pytest.raises(RuntimeError, match="finalization failed"):
            artifact_writer.finalize()
        assert not artifact_writer.container_finalized
        artifact_writer.finalize()

    assert attempts == 2
    assert artifact_writer.container_finalized


def test_replacement_metadata_must_describe_the_completed_body() -> None:
    owner = Owner()
    artifact_writer = writer(owner, io.BytesIO())
    final_metadata = header(body_length=4, body_digest="b" * 64)

    with activate_context(owner):
        with pytest.raises(RuntimeError, match="body.*complete"):
            artifact_writer._replace_metadata(final_metadata)
        artifact_writer.body.write(b"body")
        artifact_writer.close()

        with pytest.raises(TypeError, match="ArtifactHeader"):
            artifact_writer._replace_metadata(object())  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="body length"):
            artifact_writer._replace_metadata(header(body_length=3))
        with pytest.raises(ValueError, match="identity"):
            artifact_writer._replace_metadata(
                header(artifact_identity="artifact-2", body_length=4)
            )
        with pytest.raises(ValueError, match="identifier"):
            artifact_writer._replace_metadata(
                header(artifact_identifier="example.OtherV1", body_length=4)
            )
        with pytest.raises(ValueError, match="body offset"):
            artifact_writer._replace_metadata(header(body_offset=8192, body_length=4))

        artifact_writer._replace_metadata(final_metadata)

    assert artifact_writer.metadata is final_metadata


@pytest.mark.parametrize(
    ("body", "metadata", "message"),
    [
        (object(), header(), "BodyRegion"),
        (BodyRegion(io.BytesIO(), 0, 0, Owner(), writable=True), object(), "header"),
    ],
)
def test_writer_validates_constructor_arguments(
    body: object,
    metadata: object,
    message: str,
) -> None:
    with pytest.raises(TypeError, match=message):
        ArtifactWriter(body, metadata)  # type: ignore[arg-type]


def test_writer_rejects_a_noncallable_finalizer_before_body_access() -> None:
    with pytest.raises(TypeError, match="finalizer"):
        writer(Owner(), io.BytesIO(), finalizer=object())


def test_finalize_requires_the_owning_context_even_when_body_is_closed() -> None:
    owner = Owner()
    artifact_writer = writer(owner, io.BytesIO())

    with activate_context(owner):
        artifact_writer.close()

    with pytest.raises(RuntimeError, match="active context"):
        artifact_writer.finalize()
