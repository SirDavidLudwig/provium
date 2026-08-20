"""Integration tests for a successful disk-backed procedure pipeline."""

from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import UUID

import pytest
from support.provium_test_pipeline.artifacts import TextArtifact
from support.provium_test_pipeline.contracts import (
    SOURCE_PROCEDURE,
    TEXT_ARTIFACT,
    TRANSFORM_PROCEDURE,
)

from provium import (
    ArtifactHeader,
    ArtifactReadBinding,
    ArtifactReference,
    ArtifactWriteBinding,
    ProcedureExecutionResult,
    ProcedureExecutor,
    session,
)


def create_text(path: Path, text: str) -> ArtifactReference:
    result = ProcedureExecutor().execute(
        SOURCE_PROCEDURE,
        configuration_layers=({"text": text},),
        inputs={},
        outputs={"value": ArtifactWriteBinding(TextArtifact, path)},
    )
    return result.outputs["value"]


def read_text(path: Path) -> tuple[str, ArtifactHeader]:
    with session():
        with ArtifactReadBinding(TextArtifact, path).open() as reader:
            return reader.read_text(), reader.metadata


@pytest.mark.parametrize(
    ("optional_text", "expected_body", "expected_summary"),
    [
        (None, "<SRABC>", "inputs=5;characters=7"),
        ("O", "<SROABC>", "inputs=6;characters=8"),
    ],
    ids=("optional-omitted", "optional-supplied"),
)
def test_successful_pipeline_persists_bodies_metadata_and_complete_lineage(
    tmp_path: Path,
    optional_text: str | None,
    expected_body: str,
    expected_summary: str,
) -> None:
    setup_path = tmp_path / "setup.provium"
    required_path = tmp_path / "required.provium"
    repeated_paths = [tmp_path / f"repeated-{index}.provium" for index in range(3)]
    source_paths_and_text = [
        (setup_path, "S"),
        (required_path, "R"),
        *zip(repeated_paths, ("A", "B", "C"), strict=True),
    ]
    source_references = [
        create_text(path, text) for path, text in source_paths_and_text
    ]

    inputs: dict[str, object] = {
        "required": ArtifactReadBinding(TextArtifact, required_path),
        "repeated": tuple(
            ArtifactReadBinding(TextArtifact, path) for path in repeated_paths
        ),
    }
    if optional_text is not None:
        optional_path = tmp_path / "optional.provium"
        optional_reference = create_text(optional_path, optional_text)
        inputs["optional"] = ArtifactReadBinding(TextArtifact, optional_path)
        source_references.insert(2, optional_reference)

    transformed_path = tmp_path / "transformed.provium"
    summary_path = tmp_path / "summary.provium"
    result = ProcedureExecutor().execute(
        TRANSFORM_PROCEDURE,
        configuration_layers=(
            {"prefix": "<", "suffix": "overridden"},
            {"suffix": ">"},
        ),
        setup_inputs={"setup": ArtifactReadBinding(TextArtifact, setup_path)},
        inputs=inputs,
        outputs={
            "transformed": ArtifactWriteBinding(TextArtifact, transformed_path),
            "summary": ArtifactWriteBinding(TextArtifact, summary_path),
        },
    )

    transformed_body, transformed_header = read_text(transformed_path)
    summary_body, summary_header = read_text(summary_path)

    assert isinstance(result, ProcedureExecutionResult)
    assert str(UUID(result.identity)) == result.identity
    assert transformed_body == expected_body
    assert summary_body == expected_summary
    assert transformed_header.artifact_identifier == TEXT_ARTIFACT.identifier
    assert summary_header.artifact_identifier == TEXT_ARTIFACT.identifier
    assert transformed_header.body_length == len(expected_body.encode())
    assert summary_header.body_length == len(expected_summary.encode())
    assert (
        transformed_header.body_digest
        == hashlib.sha256(expected_body.encode()).hexdigest()
    )
    assert (
        summary_header.body_digest
        == hashlib.sha256(expected_summary.encode()).hexdigest()
    )

    assert result.outputs == {
        "transformed": ArtifactReference(
            transformed_header.artifact_identity,
            transformed_header.artifact_identifier,
        ),
        "summary": ArtifactReference(
            summary_header.artifact_identity,
            summary_header.artifact_identifier,
        ),
    }
    assert transformed_header.artifact_identity != summary_header.artifact_identity
    assert transformed_header.lineage == summary_header.lineage == result.lineage

    execution = result.lineage.executions[result.identity]
    assert execution.procedure == result.procedure
    assert execution.inputs == tuple(source_references)
    assert result.inputs == tuple(source_references)
    assert set(execution.outputs) == set(result.outputs.values())
    expected_references = (*source_references, *result.outputs.values())
    assert set(result.lineage.artifacts) == {
        reference.identity for reference in expected_references
    }
    assert all(
        reference.artifact_identifier == TEXT_ARTIFACT.identifier
        for reference in expected_references
    )
    assert all(
        result.lineage.artifact(reference).producer_execution_identity
        == result.identity
        for reference in result.outputs.values()
    )
