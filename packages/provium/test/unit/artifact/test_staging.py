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
    decode_header,
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
    body_digest: str | None = None,
) -> ArtifactHeader:
    reference = ArtifactReference("artifact-1", identifier)
    digest = hashlib.sha256(b"").hexdigest() if body_digest is None else body_digest
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


def test_finalize_body_streams_its_length_and_digest_from_disk(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "value.pa"
    body = b"body" * (1024 * 1024)

    with session() as owner:
        staged = stage_artifact(
            BytesArtifact.bind_write(destination),
            provisional_header(),
            owner,
        )
        staged.writer.write(body)

        assert staged.finalize_body() == (
            len(body),
            hashlib.sha256(body).hexdigest(),
        )
        assert staged.finalize_body() == (
            len(body),
            hashlib.sha256(body).hexdigest(),
        )
        assert staged.writer.closed
        assert not destination.exists()


def test_publish_writes_final_header_and_atomically_replaces_destination(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "value.pa"
    destination.write_bytes(b"existing")
    body = b"replacement"

    with session() as owner:
        staged = stage_artifact(
            BytesArtifact.bind_write(destination),
            provisional_header(),
            owner,
        )
        staged.writer.write(body)
        length, digest = staged.finalize_body()
        final_metadata = provisional_header(
            body_length=length,
            body_digest=digest,
        )

        staged.publish(final_metadata)
        staged.publish(final_metadata)
        staged.abort()

        assert staged.published
        assert not staged.aborted
        assert staged.writer.container_finalized
        assert not staged.temporary_path.exists()

    data = destination.read_bytes()
    actual = decode_header(data)
    assert actual == final_metadata
    assert data[actual.body_offset : actual.body_offset + actual.body_length] == body


def test_publish_rejects_metadata_that_does_not_match_the_body(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "value.pa"

    with session() as owner:
        staged = stage_artifact(
            BytesArtifact.bind_write(destination),
            provisional_header(),
            owner,
        )
        staged.writer.write(b"body")
        staged.finalize_body()

        with pytest.raises(ValueError, match="digest"):
            staged.publish(provisional_header(body_length=4, body_digest="b" * 64))

        assert not staged.published
        assert staged.temporary_path.exists()
        assert not destination.exists()


def test_publish_rechecks_the_body_after_its_initial_digest(tmp_path: Path) -> None:
    destination = tmp_path / "value.pa"

    with session() as owner:
        staged = stage_artifact(
            BytesArtifact.bind_write(destination),
            provisional_header(),
            owner,
        )
        staged.writer.write(b"body")
        length, digest = staged.finalize_body()
        metadata = provisional_header(body_length=length, body_digest=digest)

        with staged.temporary_path.open("r+b") as stream:
            stream.seek(metadata.body_offset)
            stream.write(b"BAD!")

        with pytest.raises(ValueError, match="digest"):
            staged.publish(metadata)

        assert not destination.exists()


def test_finalize_body_rejects_a_truncated_temporary_file(tmp_path: Path) -> None:
    with session() as owner:
        staged = stage_artifact(
            BytesArtifact.bind_write(tmp_path / "value.pa"),
            provisional_header(),
            owner,
        )
        staged.writer.write(b"body")
        staged.writer.body.flush()
        with staged.temporary_path.open("r+b") as stream:
            stream.truncate(4098)

        with pytest.raises(ValueError, match="truncated"):
            staged.finalize_body()


def test_publish_validates_metadata_type_and_final_length(tmp_path: Path) -> None:
    with session() as owner:
        staged = stage_artifact(
            BytesArtifact.bind_write(tmp_path / "value.pa"),
            provisional_header(),
            owner,
        )
        staged.writer.write(b"body")

        with pytest.raises(TypeError, match="ArtifactHeader"):
            staged.publish(object())  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="body length"):
            staged.publish(provisional_header(body_length=3))


def test_finalization_requires_an_available_owning_session(tmp_path: Path) -> None:
    with session() as owner:
        aborted = stage_artifact(
            BytesArtifact.bind_write(tmp_path / "aborted.pa"),
            provisional_header(),
            owner,
        )
        aborted.abort()
        with pytest.raises(RuntimeError, match="aborted"):
            aborted.finalize_body()

        staged = stage_artifact(
            BytesArtifact.bind_write(tmp_path / "value.pa"),
            provisional_header(),
            owner,
        )
        with session(), pytest.raises(RuntimeError, match="active session"):
            staged.finalize_body()

        owner.active = False
        try:
            with pytest.raises(RuntimeError, match="active session"):
                staged.finalize_body()
        finally:
            owner.active = True


def test_failed_atomic_replace_preserves_destination_and_cleans_staging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "value.pa"
    destination.write_bytes(b"existing")

    with session() as owner:
        staged = stage_artifact(
            BytesArtifact.bind_write(destination),
            provisional_header(),
            owner,
        )
        staged.writer.write(b"replacement")
        length, digest = staged.finalize_body()
        metadata = provisional_header(body_length=length, body_digest=digest)

        def fail_replace(_source: Path, _destination: Path) -> Path:
            raise OSError("replace failed")

        monkeypatch.setattr(Path, "replace", fail_replace)
        with pytest.raises(OSError, match="replace failed"):
            staged.publish(metadata)

        assert destination.read_bytes() == b"existing"

    assert not staged.temporary_path.exists()
