"""Tests for immutable provenance value records."""

import json

import pytest

from provium import (
    ArtifactRecord,
    ArtifactReference,
    ProcedureExecutionRecord,
    ProcedureRecord,
)


def test_artifact_reference_and_record_validate_required_values() -> None:
    reference = ArtifactReference("artifact-1", "example.ImageV1")
    record = ArtifactRecord(reference, "abc123", "execution-1")

    assert record.reference is reference
    assert record.body_digest == "abc123"
    assert record.producer_execution_identity == "execution-1"

    for invalid_identity in ("", "   "):
        with pytest.raises(ValueError, match="identity"):
            ArtifactReference(invalid_identity, "example.ImageV1")
    with pytest.raises(ValueError, match="artifact_identifier"):
        ArtifactReference("artifact-1", "")
    with pytest.raises(TypeError, match="identity"):
        ArtifactReference(object(), "example.ImageV1")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="reference"):
        ArtifactRecord(object(), "abc123", "execution-1")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="body_digest"):
        ArtifactRecord(reference, "", "execution-1")
    with pytest.raises(ValueError, match="producer_execution_identity"):
        ArtifactRecord(reference, "abc123", "")


def test_procedure_record_preserves_its_configuration_snapshot() -> None:
    procedure = ProcedureRecord(
        "example.DetectV1",
        "contract-digest",
        config={"threshold": 0.5},
        config_codec="provium-config-v1",
    )

    assert procedure.config == {"threshold": 0.5}
    assert procedure.config_codec == "provium-config-v1"

    with pytest.raises(ValueError, match="name"):
        ProcedureRecord("", "contract-digest")
    with pytest.raises(ValueError, match="version"):
        ProcedureRecord("example.DetectV1", "")
    with pytest.raises(ValueError, match="config_codec"):
        ProcedureRecord("example.DetectV1", "contract-digest", config_codec="")


def test_execution_preserves_input_order_and_rejects_invalid_graph_values() -> None:
    first = ArtifactReference("first", "example.ImageV1")
    second = ArtifactReference("second", "example.ImageV1")
    output = ArtifactReference("output", "example.ImageV1")
    procedure = ProcedureRecord("example.JoinV1", "contract-digest")

    execution = ProcedureExecutionRecord(
        "execution-1",
        procedure,
        inputs=(second, first),
        outputs=(output,),
    )

    assert execution.inputs == (second, first)
    assert execution.outputs == (output,)
    input_only = ProcedureExecutionRecord(
        "execution-2",
        procedure,
        inputs=(first,),
        outputs=None,
    )
    assert input_only.inputs == (first,)
    assert input_only.outputs == ()

    with pytest.raises(ValueError, match="identity"):
        ProcedureExecutionRecord("", procedure, outputs=(output,))
    with pytest.raises(TypeError, match="procedure"):
        ProcedureExecutionRecord("execution-1", object(), outputs=(output,))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="at least one input or output"):
        ProcedureExecutionRecord("execution-1", procedure)
    with pytest.raises(TypeError, match="input.*artifact references"):
        ProcedureExecutionRecord(
            "execution-1",
            procedure,
            inputs=(object(),),  # type: ignore[arg-type]
            outputs=(output,),
        )
    with pytest.raises(ValueError, match="duplicate input"):
        ProcedureExecutionRecord(
            "execution-1",
            procedure,
            inputs=(first, first),
            outputs=(output,),
        )
    with pytest.raises(ValueError, match="duplicate output"):
        ProcedureExecutionRecord(
            "execution-1",
            procedure,
            outputs=(output, output),
        )
    with pytest.raises(ValueError, match="both an input and an output"):
        ProcedureExecutionRecord(
            "execution-1",
            procedure,
            inputs=(output,),
            outputs=(output,),
        )


@pytest.mark.parametrize(
    "record",
    [
        ArtifactReference("artifact-1", "example.ImageV1"),
        ArtifactRecord(
            ArtifactReference("artifact-1", "example.ImageV1"),
            "abc123",
            "execution-1",
        ),
        ProcedureRecord(
            "example.DetectV1",
            "contract-digest",
            {"threshold": 0.5},
            "provium-config-v1",
        ),
        ProcedureExecutionRecord(
            "execution-1",
            ProcedureRecord("example.DetectV1", "contract-digest"),
            inputs=(ArtifactReference("input", "example.ImageV1"),),
            outputs=(ArtifactReference("output", "example.ImageV1"),),
        ),
    ],
)
def test_provenance_records_round_trip_canonical_json(record: object) -> None:
    encoded = record.to_json()  # type: ignore[attr-defined]

    assert type(record).from_json(encoded) == record  # type: ignore[attr-defined]
    assert encoded == json.dumps(
        record.to_dict(),  # type: ignore[attr-defined]
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def test_provenance_deserialization_rejects_invalid_shapes() -> None:
    with pytest.raises(ValueError, match="artifact reference"):
        ArtifactReference.from_dict({"identity": "artifact-1"})
    with pytest.raises(TypeError, match="JSON object"):
        ArtifactReference.from_json("[]")
