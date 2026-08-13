from __future__ import annotations

import hashlib
import io
from pathlib import Path

from provium import (
    ArtifactHeader,
    ArtifactLineage,
    ArtifactRecord,
    ArtifactReference,
    ProcedureExecutionRecord,
    ProcedureRecord,
    encode_header,
)
from provium.cli.application import run


def write_artifact(path: Path, body: bytes = b"hello") -> ArtifactHeader:
    reference = ArtifactReference("artifact-1", "example.BytesV1")
    execution = ProcedureExecutionRecord(
        "execution-1",
        ProcedureRecord("produce", "1"),
        outputs=(reference,),
    )
    digest = hashlib.sha256(body).hexdigest()
    lineage = ArtifactLineage.for_execution(
        execution,
        (ArtifactRecord(reference, digest, execution.identity),),
    )
    header = ArtifactHeader(
        artifact_identifier=reference.artifact_identifier,
        artifact_identity=reference.identity,
        body_offset=4096,
        body_length=len(body),
        body_digest=digest,
        lineage=lineage,
    )
    encoded = encode_header(header)
    path.write_bytes(encoded + bytes(header.body_offset - len(encoded)) + body)
    return header


def test_inspect_prints_artifact_metadata(tmp_path: Path) -> None:
    path = tmp_path / "artifact.pa"
    header = write_artifact(path)
    stdout = io.StringIO()

    result = run(["inspect", str(path)], stdout=stdout, stderr=io.StringIO())

    assert result == 0
    assert stdout.getvalue() == (
        f"Path: {path}\n"
        f"Artifact type: {header.artifact_identifier}\n"
        f"Artifact identity: {header.artifact_identity}\n"
        f"Body size: {header.body_length} bytes\n"
        f"SHA-256: {header.body_digest}\n"
        "Produced by: produce 1\n"
        "Lineage: 1 artifact, 1 execution\n"
    )


def test_inspect_reports_a_malformed_artifact(tmp_path: Path) -> None:
    path = tmp_path / "invalid.pa"
    path.write_bytes(b"not an artifact")
    stderr = io.StringIO()

    result = run(["inspect", str(path)], stdout=io.StringIO(), stderr=stderr)

    assert result == 1
    assert stderr.getvalue() == "provium: truncated fixed header\n"


def test_inspect_uses_plural_lineage_labels(tmp_path: Path) -> None:
    path = tmp_path / "artifact.pa"
    header = write_artifact(path)
    second_reference = ArtifactReference("artifact-2", "example.BytesV1")
    second_execution = ProcedureExecutionRecord(
        "execution-2",
        ProcedureRecord("copy", "1"),
        inputs=(
            ArtifactReference(header.artifact_identity, header.artifact_identifier),
        ),
        outputs=(second_reference,),
    )
    second_digest = hashlib.sha256(b"copy").hexdigest()
    lineage = header.lineage
    lineage = ArtifactLineage.for_execution(
        second_execution,
        (ArtifactRecord(second_reference, second_digest, second_execution.identity),),
        (lineage,),
    )
    expanded = ArtifactHeader(
        artifact_identifier=second_reference.artifact_identifier,
        artifact_identity=second_reference.identity,
        body_offset=4096,
        body_length=4,
        body_digest=second_digest,
        lineage=lineage,
    )
    encoded = encode_header(expanded)
    path.write_bytes(encoded + bytes(expanded.body_offset - len(encoded)) + b"copy")
    stdout = io.StringIO()

    assert run(["inspect", str(path)], stdout=stdout, stderr=io.StringIO()) == 0
    assert "Lineage: 2 artifacts, 2 executions\n" in stdout.getvalue()
