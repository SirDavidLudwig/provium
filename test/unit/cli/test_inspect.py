from __future__ import annotations

import hashlib
import importlib
import io
from pathlib import Path

import pytest

from provium import (
    Artifact,
    ArtifactCatalog,
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
)
from provium.cli.application import run
from provium.cli.commands.inspect import _render_inspection


class InspectingReader(ArtifactReader):
    def inspect(self) -> object:
        return {"summary": "hello", "custom": object()}


class PlainReader(ArtifactReader):
    pass


class Writer(ArtifactWriter):
    pass


InspectingArtifact = Artifact("example.BytesV1", "Inspecting", InspectingReader, Writer)


PlainArtifact = Artifact("example.BytesV1", "Plain", PlainReader, Writer)


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


def test_inspect_body_reports_an_unlocated_artifact_type(tmp_path: Path) -> None:
    path = tmp_path / "artifact.pa"
    write_artifact(path)
    stdout = io.StringIO()

    result = run(["inspect", "--body", str(path)], stdout=stdout, stderr=io.StringIO())

    assert result == 0
    assert stdout.getvalue().endswith(
        "\nBody inspection unavailable: artifact type could not be located.\n"
    )


def test_inspect_body_reports_a_missing_inspector(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "artifact.pa"
    write_artifact(path)
    catalog = ArtifactCatalog()
    catalog.register(
        ArtifactDefinition(
            "example.BytesV1", f"{__name__}:PlainArtifact", "Plain bytes."
        )
    )
    monkeypatch.setattr(
        "provium.cli.commands.inspect.discover_catalogs", lambda: catalog
    )
    session_module = importlib.import_module("provium.session")
    monkeypatch.setattr(session_module, "discover_catalogs", lambda: catalog)
    stdout = io.StringIO()

    result = run(["inspect", "--body", str(path)], stdout=stdout, stderr=io.StringIO())

    assert result == 0
    assert stdout.getvalue().endswith(
        "\nBody inspection unavailable: artifact type does not provide an inspector.\n"
    )


def test_inspect_body_renders_the_reader_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "artifact.pa"
    write_artifact(path)
    catalog = ArtifactCatalog()
    catalog.register(
        ArtifactDefinition(
            "example.BytesV1", f"{__name__}:InspectingArtifact", "Inspectable bytes."
        )
    )
    monkeypatch.setattr(
        "provium.cli.commands.inspect.discover_catalogs", lambda: catalog
    )
    session_module = importlib.import_module("provium.session")
    monkeypatch.setattr(session_module, "discover_catalogs", lambda: catalog)
    stdout = io.StringIO()

    result = run(["inspect", "--body", str(path)], stdout=stdout, stderr=io.StringIO())

    assert result == 0
    assert (
        '\nInspected body:\n{\n  "summary": "hello",\n  "custom": "<object object at '
        in stdout.getvalue()
    )


def test_inspection_rendering_falls_back_to_repr_for_a_cycle() -> None:
    value: list[object] = []
    value.append(value)

    assert _render_inspection(value) == "[[...]]"
