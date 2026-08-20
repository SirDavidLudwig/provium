"""Tests for disk-backed staged artifact outputs."""

import hashlib
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
    StagedArtifact,
    session,
    stage_artifact,
)


class Reader(ArtifactReader):
    pass


class Writer(ArtifactWriter):
    def write(self, value: bytes) -> int:
        return self.body.write(value)


DEFINITION = ArtifactDefinition(
    identifier="example.BytesV1",
    target=f"{__name__}:BytesArtifact",
    description="Bytes.",
)


class BytesArtifact(Artifact[Reader, Writer]):
    definition = DEFINITION
    reader = Reader
    writer = Writer


class BrokenWriter(ArtifactWriter):
    def __init__(self, *args: object, **kwargs: object) -> None:
        raise RuntimeError("writer construction failed")


class BrokenArtifact(Artifact[Reader, BrokenWriter]):
    definition = ArtifactDefinition(
        identifier="example.BrokenV1",
        target=f"{__name__}:BrokenArtifact",
        description="Broken writer.",
    )
    reader = Reader
    writer = BrokenWriter


def provisional_header(
    identifier: str = DEFINITION.identifier,
    *,
    body_length: int = 0,
) -> ArtifactHeader:
    reference = ArtifactReference("artifact-1", identifier)
    digest = hashlib.sha256(b"").hexdigest()
    execution = ProcedureExecutionRecord(
        "execution-1",
        ProcedureRecord("example.CreateV1", "contract-digest"),
        outputs=(reference,),
    )
    lineage = ArtifactLineage.for_execution(
        execution,
        (ArtifactRecord(reference, digest, execution.identity),),
    )
    return ArtifactHeader(
        artifact_identifier=reference.artifact_identifier,
        artifact_identity=reference.identity,
        body_offset=4096,
        body_length=body_length,
        body_digest=digest,
        lineage=lineage,
    )


def test_stage_artifact_creates_a_typed_disk_backed_temporary_output(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "value.pa"

    with session() as owner:
        staged = stage_artifact(
            BytesArtifact.bind_write(destination),
            provisional_header(),
            owner,
        )
        assert isinstance(staged, StagedArtifact)
        assert isinstance(staged.writer, Writer)
        assert staged.destination == destination
        assert staged.temporary_path.parent == destination.parent
        assert staged.temporary_path != destination
        assert staged.temporary_path.exists()
        assert not destination.exists()

        staged.writer.write(b"body")
        staged.writer.body.flush()
        assert staged.temporary_path.stat().st_size == 4100
        assert staged.temporary_path.read_bytes()[4096:] == b"body"

        staged.abort()

    assert staged.aborted
    assert staged.writer.closed
    assert not staged.temporary_path.exists()
    assert not destination.exists()


def test_staging_preserves_an_existing_destination(tmp_path: Path) -> None:
    destination = tmp_path / "value.pa"
    destination.write_bytes(b"existing")

    with session() as owner:
        staged = stage_artifact(
            BytesArtifact.bind_write(destination),
            provisional_header(),
            owner,
        )
        staged.writer.write(b"replacement")
        staged.abort()

    assert destination.read_bytes() == b"existing"


def test_abort_is_idempotent(tmp_path: Path) -> None:
    with session() as owner:
        staged = stage_artifact(
            BytesArtifact.bind_write(tmp_path / "value.pa"),
            provisional_header(),
            owner,
        )
        staged.abort()
        staged.abort()


def test_staging_requires_matching_artifact_metadata(tmp_path: Path) -> None:
    reference = ArtifactReference("artifact-1", "example.OtherV1")
    digest = hashlib.sha256(b"").hexdigest()
    execution = ProcedureExecutionRecord(
        "execution-1",
        ProcedureRecord("example.CreateV1", "contract-digest"),
        outputs=(reference,),
    )
    metadata = ArtifactHeader(
        artifact_identifier=reference.artifact_identifier,
        artifact_identity=reference.identity,
        body_offset=4096,
        body_length=0,
        body_digest=digest,
        lineage=ArtifactLineage.for_execution(
            execution,
            (ArtifactRecord(reference, digest, execution.identity),),
        ),
    )

    with session() as owner, pytest.raises(ValueError, match="artifact identifier"):
        stage_artifact(BytesArtifact.bind_write(tmp_path / "value.pa"), metadata, owner)


def test_staging_requires_the_active_owner(tmp_path: Path) -> None:
    owner = session()
    with pytest.raises(RuntimeError, match="active session"):
        stage_artifact(
            BytesArtifact.bind_write(tmp_path / "value.pa"),
            provisional_header(),
            owner,
        )

    with owner:
        with session(), pytest.raises(RuntimeError, match="active session"):
            stage_artifact(
                BytesArtifact.bind_write(tmp_path / "value.pa"),
                provisional_header(),
                owner,
            )


def test_staging_requires_valid_empty_provisional_metadata(tmp_path: Path) -> None:
    binding = BytesArtifact.bind_write(tmp_path / "value.pa")

    with session() as owner:
        with pytest.raises(TypeError, match="ArtifactHeader"):
            stage_artifact(binding, object(), owner)  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="empty body"):
            stage_artifact(binding, provisional_header(body_length=1), owner)


def test_writer_construction_failure_removes_the_temporary_file(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "value.pa"

    with session() as owner, pytest.raises(RuntimeError, match="construction failed"):
        stage_artifact(
            BrokenArtifact.bind_write(destination),
            provisional_header(BrokenArtifact.definition.identifier),
            owner,
        )

    assert not destination.exists()
    assert not list(tmp_path.glob(".*.tmp"))
