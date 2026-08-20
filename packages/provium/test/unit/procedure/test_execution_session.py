"""Tests for low-level procedure execution sessions."""

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
    ProcedureExecutionSession,
    ProcedureRecord,
    decode_header,
    encode_header,
    session,
)


class BytesReader(ArtifactReader):
    def read(self) -> bytes:
        return self.body.read()


class BytesWriter(ArtifactWriter):
    def write(self, value: bytes) -> int:
        return self.body.write(value)


DEFINITION = ArtifactDefinition(
    identifier="example.BytesV1",
    target=f"{__name__}:BytesArtifact",
    description="Bytes.",
)


class BytesArtifact(Artifact[BytesReader, BytesWriter]):
    definition = DEFINITION
    reader = BytesReader
    writer = BytesWriter


PROCEDURE = ProcedureRecord("example.CopyV1", "contract-digest")


def write_source(path: Path, body: bytes = b"source") -> ArtifactRecord:
    reference = ArtifactReference("source-artifact", DEFINITION.identifier)
    digest = hashlib.sha256(body).hexdigest()
    execution = ProcedureExecutionRecord(
        "source-execution",
        ProcedureRecord("example.SourceV1", "source-contract"),
        outputs=(reference,),
    )
    record = ArtifactRecord(reference, digest, execution.identity)
    lineage = ArtifactLineage.for_execution(execution, (record,))
    header = ArtifactHeader.create(
        artifact_identifier=reference.artifact_identifier,
        artifact_identity=reference.identity,
        body_length=len(body),
        body_digest=digest,
        lineage=lineage,
    )
    encoded = encode_header(header)
    path.write_bytes(encoded + body)
    return record


def test_execution_publishes_output_with_inherited_input_lineage(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "source.pa"
    source_record = write_source(source_path)
    destination = tmp_path / "output.pa"

    with session():
        source = BytesArtifact.bind_read(source_path).open()
        with ProcedureExecutionSession(PROCEDURE) as execution:
            writers = execution.stage_outputs(
                {"output": BytesArtifact.bind_write(destination)}
            )
            writer = writers["output"]
            assert isinstance(writer, BytesWriter)
            writer.write(source.read())
            assert not destination.exists()

        assert execution.writers == (writer,)
        assert len(execution.outputs) == 1
        assert execution.lineage is not None

    data = destination.read_bytes()
    header = decode_header(data)
    produced = header.lineage.producing_execution(
        ArtifactReference(header.artifact_identity, header.artifact_identifier)
    )
    assert produced.identity == execution.identity
    assert produced.procedure == PROCEDURE
    assert produced.inputs == (source_record.reference,)
    assert produced.outputs == execution.outputs
    assert header.lineage.artifact(source_record.reference) == source_record
    assert (
        data[header.body_offset : header.body_offset + header.body_length] == b"source"
    )


def test_each_execution_has_a_fresh_identity(tmp_path: Path) -> None:
    identities: list[str] = []

    with session():
        for index in range(2):
            with ProcedureExecutionSession(PROCEDURE) as execution:
                execution.stage_outputs(
                    {"output": BytesArtifact.bind_write(tmp_path / f"{index}.pa")}
                )
            identities.append(execution.identity)

    assert len(set(identities)) == 2


def test_multiple_outputs_share_one_complete_execution_record(tmp_path: Path) -> None:
    destinations = [tmp_path / "first.pa", tmp_path / "second.pa"]

    with session(), ProcedureExecutionSession(PROCEDURE) as execution:
        writers = execution.stage_outputs(
            {
                "first": BytesArtifact.bind_write(destinations[0]),
                "second": BytesArtifact.bind_write(destinations[1]),
            }
        )
        writers["first"].body.write(b"first")
        writers["second"].body.write(b"second")

    headers = [decode_header(path.read_bytes()) for path in destinations]
    assert headers[0].lineage == headers[1].lineage
    assert {
        reference.identity
        for reference in headers[0].lineage.executions[execution.identity].outputs
    } == {reference.identity for reference in execution.outputs}


def test_failed_execution_abandons_outputs_and_preserves_destinations(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "output.pa"
    destination.write_bytes(b"existing")

    with session(), pytest.raises(RuntimeError, match="processing failed"):
        with ProcedureExecutionSession(PROCEDURE) as execution:
            writer = execution.stage_outputs(
                {"output": BytesArtifact.bind_write(destination)}
            )["output"]
            writer.body.write(b"replacement")
            raise RuntimeError("processing failed")

    assert destination.read_bytes() == b"existing"
    assert not list(tmp_path.glob(".*.tmp"))


def test_execution_requires_an_active_parent_and_one_output_staging_call(
    tmp_path: Path,
) -> None:
    execution = ProcedureExecutionSession(PROCEDURE)
    with pytest.raises(RuntimeError, match="active session"):
        execution.__enter__()

    with session(), execution:
        with pytest.raises(ValueError, match="at least one output"):
            execution.stage_outputs({})
        execution.stage_outputs(
            {"output": BytesArtifact.bind_write(tmp_path / "output.pa")}
        )
        with pytest.raises(RuntimeError, match="already been staged"):
            execution.stage_outputs(
                {"other": BytesArtifact.bind_write(tmp_path / "other.pa")}
            )

    with session(), pytest.raises(RuntimeError, match="already been entered"):
        execution.__enter__()


def test_execution_validates_constructor_and_requires_staged_outputs() -> None:
    with pytest.raises(TypeError, match="ProcedureRecord"):
        ProcedureExecutionSession(object())  # type: ignore[arg-type]

    execution = ProcedureExecutionSession(PROCEDURE)
    assert execution.writers == ()
    with session(), pytest.raises(RuntimeError, match="have not been staged"):
        with execution:
            pass


def test_output_staging_rejects_duplicate_destinations(tmp_path: Path) -> None:
    destination = tmp_path / "output.pa"

    with session(), ProcedureExecutionSession(PROCEDURE) as execution:
        with pytest.raises(ValueError, match="destination"):
            execution.stage_outputs(
                {
                    "first": BytesArtifact.bind_write(destination),
                    "second": BytesArtifact.bind_write(destination),
                }
            )
        execution.stage_outputs({"output": BytesArtifact.bind_write(destination)})


def test_output_staging_requires_its_execution_child_to_remain_active(
    tmp_path: Path,
) -> None:
    with session(), ProcedureExecutionSession(PROCEDURE) as execution:
        with session(), pytest.raises(RuntimeError, match="not active"):
            execution.stage_outputs(
                {"output": BytesArtifact.bind_write(tmp_path / "nested.pa")}
            )

        child = execution._session
        assert child is not None
        child.active = False
        try:
            with pytest.raises(RuntimeError, match="not active"):
                execution.stage_outputs(
                    {"output": BytesArtifact.bind_write(tmp_path / "inactive.pa")}
                )
        finally:
            child.active = True

        execution.stage_outputs(
            {"output": BytesArtifact.bind_write(tmp_path / "output.pa")}
        )


def test_multi_output_publication_failure_restores_every_destination(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = tmp_path / "first.pa"
    second = tmp_path / "second.pa"
    first.write_bytes(b"original-first")
    second.write_bytes(b"original-second")
    original_replace = Path.replace

    def fail_second_publish(source: Path, destination: Path) -> Path:
        if source.name.endswith(".tmp") and destination == second:
            raise OSError("second publish failed")
        return original_replace(source, destination)

    monkeypatch.setattr(Path, "replace", fail_second_publish)

    with session(), pytest.raises(OSError, match="second publish failed"):
        with ProcedureExecutionSession(PROCEDURE) as execution:
            writers = execution.stage_outputs(
                {
                    "first": BytesArtifact.bind_write(first),
                    "second": BytesArtifact.bind_write(second),
                }
            )
            writers["first"].body.write(b"new-first")
            writers["second"].body.write(b"new-second")

    assert first.read_bytes() == b"original-first"
    assert second.read_bytes() == b"original-second"
    assert not list(tmp_path.glob(".*.tmp"))
    assert not list(tmp_path.glob(".*.backup"))


def test_successful_publication_removes_destination_backups(tmp_path: Path) -> None:
    destination = tmp_path / "output.pa"
    destination.write_bytes(b"existing")

    with session(), ProcedureExecutionSession(PROCEDURE) as execution:
        writer = execution.stage_outputs(
            {"output": BytesArtifact.bind_write(destination)}
        )["output"]
        writer.body.write(b"replacement")

    assert decode_header(destination.read_bytes()).body_length == len(b"replacement")
    assert not list(tmp_path.glob(".*.backup"))


def test_failed_multi_output_publication_removes_new_destinations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = tmp_path / "first.pa"
    second = tmp_path / "second.pa"
    original_replace = Path.replace

    def fail_second_publish(source: Path, destination: Path) -> Path:
        if source.name.endswith(".tmp") and destination == second:
            raise OSError("second publish failed")
        return original_replace(source, destination)

    monkeypatch.setattr(Path, "replace", fail_second_publish)

    with session(), pytest.raises(OSError, match="second publish failed"):
        with ProcedureExecutionSession(PROCEDURE) as execution:
            writers = execution.stage_outputs(
                {
                    "first": BytesArtifact.bind_write(first),
                    "second": BytesArtifact.bind_write(second),
                }
            )
            writers["first"].body.write(b"first")
            writers["second"].body.write(b"second")

    assert not first.exists()
    assert not second.exists()


def test_publication_preserves_original_error_when_restoration_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = tmp_path / "first.pa"
    second = tmp_path / "second.pa"
    first.write_bytes(b"original-first")
    second.write_bytes(b"original-second")
    original_replace = Path.replace

    def fail_publish_and_restore(source: Path, destination: Path) -> Path:
        if source.name.endswith(".tmp") and destination == second:
            raise OSError("publish failed")
        if source.name.endswith(".backup"):
            raise RuntimeError("restore failed")
        return original_replace(source, destination)

    monkeypatch.setattr(Path, "replace", fail_publish_and_restore)

    with session(), pytest.raises(OSError, match="publish failed") as caught:
        with ProcedureExecutionSession(PROCEDURE) as execution:
            execution.stage_outputs(
                {
                    "first": BytesArtifact.bind_write(first),
                    "second": BytesArtifact.bind_write(second),
                }
            )

    assert isinstance(caught.value.__cause__, RuntimeError)
    assert str(caught.value.__cause__) == "restore failed"
