from __future__ import annotations

import json

import pytest

from provium.provenance import (
    ArtifactRecord,
    ArtifactReference,
    ProcedureExecutionRecord,
    ProcedureRecord,
)


def test_artifact_reference_validates_required_values() -> None:
    reference = ArtifactReference(
        identity="artifact-1", artifact_identifier="example.IntegerV1"
    )

    assert reference.identity == "artifact-1"
    assert reference.artifact_identifier == "example.IntegerV1"
    with pytest.raises(ValueError, match="identity"):
        ArtifactReference(identity="", artifact_identifier="example.IntegerV1")
    with pytest.raises(ValueError, match="artifact_identifier"):
        ArtifactReference(identity="artifact-1", artifact_identifier="")


def test_artifact_record_validates_digest_and_producer() -> None:
    reference = ArtifactReference("artifact-1", "example.IntegerV1")
    record = ArtifactRecord(reference, "abc123", "execution-1")

    assert record.reference is reference
    assert record.body_digest == "abc123"
    assert record.producer_execution_identity == "execution-1"
    with pytest.raises(ValueError, match="body_digest"):
        ArtifactRecord(reference, "", "execution-1")
    with pytest.raises(ValueError, match="producer_execution_identity"):
        ArtifactRecord(reference, "abc123", "")
    with pytest.raises(TypeError, match="reference"):
        ArtifactRecord("not-a-reference", "abc123", "execution-1")  # type: ignore[arg-type]


def test_procedure_record_validates_identity_and_preserves_config_snapshot() -> None:
    procedure = ProcedureRecord(
        name="add",
        version="1",
        config={"nested": [None, True, 3, "value"]},
        config_codec="json-v1",
    )

    assert procedure.config == {"nested": [None, True, 3, "value"]}
    assert procedure.config_codec == "json-v1"
    with pytest.raises(ValueError, match="name"):
        ProcedureRecord(name="", version="1")
    with pytest.raises(ValueError, match="version"):
        ProcedureRecord(name="add", version="")


@pytest.mark.parametrize("input_count", [0, 1, 3])
@pytest.mark.parametrize("output_count", [1, 2])
def test_procedure_execution_supports_expected_input_and_output_cardinality(
    input_count: int, output_count: int
) -> None:
    inputs = tuple(
        ArtifactReference(f"input-{i}", "example.IntegerV1") for i in range(input_count)
    )
    outputs = tuple(
        ArtifactReference(f"output-{i}", "example.IntegerV1")
        for i in range(output_count)
    )

    execution = ProcedureExecutionRecord(
        identity="execution-1",
        procedure=ProcedureRecord("add", "1"),
        inputs=inputs,
        outputs=outputs,
    )

    assert execution.inputs == inputs
    assert execution.outputs == outputs


def test_procedure_execution_requires_identity_and_outputs() -> None:
    procedure = ProcedureRecord("add", "1")
    output = ArtifactReference("output-1", "example.IntegerV1")

    with pytest.raises(ValueError, match="identity"):
        ProcedureExecutionRecord("", procedure, outputs=(output,))
    with pytest.raises(ValueError, match="output"):
        ProcedureExecutionRecord("execution-1", procedure)
    with pytest.raises(ValueError, match="duplicate input"):
        ProcedureExecutionRecord("execution-1", procedure, (output, output), (output,))
    with pytest.raises(ValueError, match="duplicate output"):
        ProcedureExecutionRecord("execution-1", procedure, outputs=(output, output))
    with pytest.raises(TypeError, match="procedure"):
        ProcedureExecutionRecord("execution-1", "not-a-procedure", outputs=(output,))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="artifact references"):
        ProcedureExecutionRecord("execution-1", procedure, outputs=("not-a-reference",))  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "model",
    [
        ArtifactReference("artifact-1", "example.IntegerV1"),
        ArtifactRecord(
            ArtifactReference("artifact-1", "example.IntegerV1"),
            "abc123",
            "execution-1",
        ),
        ProcedureRecord("add", "1", {"amount": 2}, "json-v1"),
        ProcedureExecutionRecord(
            "execution-1",
            ProcedureRecord("add", "1"),
            (ArtifactReference("input-1", "example.IntegerV1"),),
            (ArtifactReference("output-1", "example.IntegerV1"),),
        ),
    ],
)
def test_models_round_trip_without_information_loss(model: object) -> None:
    encoded = model.to_json()  # type: ignore[attr-defined]

    assert type(model).from_json(encoded) == model  # type: ignore[attr-defined]
    assert json.dumps(model.to_dict(), sort_keys=True, separators=(",", ":")) == encoded  # type: ignore[attr-defined]


def test_deserialization_rejects_wrong_model_shape() -> None:
    with pytest.raises(ValueError, match="artifact reference"):
        ArtifactReference.from_dict({"identity": "only-one-field"})
    with pytest.raises(TypeError, match="JSON object"):
        ArtifactReference.from_json("[]")
