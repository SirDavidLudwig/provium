from __future__ import annotations

import hashlib
import io
from pathlib import Path

import pytest

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


def write_artifact(path: Path) -> ArtifactHeader:
    body = b"hello"
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


@pytest.mark.parametrize(
    ("arguments", "function", "value"),
    [
        ([], "render_mermaid", b"mermaid image"),
        (["--renderer", "mermaid"], "render_mermaid", b"mermaid image"),
        (["--renderer", "graphviz"], "render_lineage", b"graphviz image"),
    ],
)
def test_graph_renders_images_with_selected_renderer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    arguments: list[str],
    function: str,
    value: bytes,
) -> None:
    artifact_path = tmp_path / "artifact.pa"
    output_path = tmp_path / "lineage.svg"
    header = write_artifact(artifact_path)
    received: list[tuple[object, str]] = []

    def render(lineage: object, *, format: str) -> bytes:
        received.append((lineage, format))
        return value

    monkeypatch.setattr(f"provium.cli.commands.graph.{function}", render)

    result = run(
        ["graph", *arguments, str(artifact_path), str(output_path)],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )

    assert result == 0
    assert output_path.read_bytes() == value
    assert received == [(header.lineage, "svg")]


@pytest.mark.parametrize(
    ("renderer", "extension", "function", "source"),
    [
        ("mermaid", ".mmd", "lineage_to_mermaid", "mermaid source\n"),
        ("graphviz", ".dot", "lineage_to_dot", "digraph source\n"),
    ],
)
def test_graph_writes_source_for_renderer_native_extensions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    renderer: str,
    extension: str,
    function: str,
    source: str,
) -> None:
    artifact_path = tmp_path / "artifact.pa"
    output_path = tmp_path / f"lineage{extension}"
    header = write_artifact(artifact_path)
    received: list[object] = []

    def generate(lineage: object) -> str:
        received.append(lineage)
        return source

    monkeypatch.setattr(f"provium.cli.commands.graph.{function}", generate)

    result = run(
        [
            "graph",
            "--renderer",
            renderer,
            str(artifact_path),
            str(output_path),
        ],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )

    assert result == 0
    assert output_path.read_text() == source
    assert received == [header.lineage]


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ([], "extension"),
        (["--renderer", "graphviz", "output.mmd"], "requires mermaid"),
        (["--renderer", "mermaid", "output.dot"], "requires graphviz"),
        (["output.txt"], "unsupported"),
    ],
)
def test_graph_rejects_incompatible_or_unknown_output(
    tmp_path: Path,
    arguments: list[str],
    message: str,
) -> None:
    artifact_path = tmp_path / "artifact.pa"
    write_artifact(artifact_path)
    output = arguments[-1] if arguments and "." in arguments[-1] else "output"
    prefix = arguments[:-1] if output != "output" else arguments
    stderr = io.StringIO()

    result = run(
        ["graph", *prefix, str(artifact_path), str(tmp_path / output)],
        stdout=io.StringIO(),
        stderr=stderr,
    )

    assert result == 1
    assert message in stderr.getvalue()
