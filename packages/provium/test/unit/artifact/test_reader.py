"""Tests for typed artifact readers."""

import io
from dataclasses import dataclass

import pytest

from provium import (
    ArtifactHeader,
    ArtifactLineage,
    ArtifactReader,
    ArtifactRecord,
    ArtifactReference,
    BodyRegion,
    ProcedureExecutionRecord,
    ProcedureRecord,
)
from provium.artifact.reader import INSPECTION_UNAVAILABLE
from provium.context import activate_context


@dataclass
class Owner:
    active: bool = True


def header() -> ArtifactHeader:
    reference = ArtifactReference("artifact-1", "example.BytesV1")
    execution = ProcedureExecutionRecord(
        "execution-1",
        ProcedureRecord("example.CreateV1", "contract-digest"),
        outputs=(reference,),
    )
    lineage = ArtifactLineage.for_execution(
        execution,
        (ArtifactRecord(reference, "a" * 64, execution.identity),),
    )
    return ArtifactHeader(
        artifact_identifier=reference.artifact_identifier,
        artifact_identity=reference.identity,
        body_offset=4096,
        body_length=4,
        body_digest="a" * 64,
        lineage=lineage,
    )


def test_reader_exposes_metadata_identity_lineage_and_bounded_body() -> None:
    owner = Owner()
    metadata = header()
    body = BodyRegion(io.BytesIO(bytes(4096) + b"body"), 4096, 4, owner)
    reader = ArtifactReader(body, metadata)

    assert reader.metadata is metadata
    assert reader.identity == "artifact-1"
    assert reader.artifact_identifier == "example.BytesV1"
    assert reader.lineage is metadata.lineage
    assert not reader.closed
    assert reader.inspect() is INSPECTION_UNAVAILABLE
    with activate_context(owner):
        assert reader.body is body
        assert reader.body.read() == b"body"


def test_reader_is_a_context_manager_that_closes_its_body() -> None:
    owner = Owner()
    body = BodyRegion(io.BytesIO(b"body"), 0, 4, owner)
    reader = ArtifactReader(body, header())

    with activate_context(owner):
        with reader as entered:
            assert entered is reader
            assert not reader.closed
        assert reader.closed
        reader.close()


def test_reader_body_access_requires_its_active_context() -> None:
    reader = ArtifactReader(
        BodyRegion(io.BytesIO(b"body"), 0, 4, Owner()),
        header(),
    )

    with pytest.raises(RuntimeError, match="active context"):
        _ = reader.body
    with pytest.raises(RuntimeError, match="active context"):
        reader.__enter__()


def test_reader_rejects_a_body_length_that_disagrees_with_its_header() -> None:
    with pytest.raises(ValueError, match="body length.*header"):
        ArtifactReader(
            BodyRegion(io.BytesIO(b"short"), 0, 5, Owner()),
            header(),
        )


@pytest.mark.parametrize(
    ("body", "metadata", "message"),
    [
        (object(), header(), "BodyRegion"),
        (BodyRegion(io.BytesIO(), 0, 0, Owner()), object(), "ArtifactHeader"),
    ],
)
def test_reader_validates_constructor_arguments(
    body: object,
    metadata: object,
    message: str,
) -> None:
    with pytest.raises(TypeError, match=message):
        ArtifactReader(body, metadata)  # type: ignore[arg-type]
