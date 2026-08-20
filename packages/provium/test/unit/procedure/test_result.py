"""Tests for immutable procedure execution results."""

from types import MappingProxyType

import pytest

from provium import (
    ArtifactLineage,
    ArtifactReference,
    ProcedureExecutionResult,
    ProcedureRecord,
)

REFERENCE = ArtifactReference("artifact", "example.ArtifactV1")
PROCEDURE = ProcedureRecord("example.ProcedureV1", "contract-digest")


def test_execution_result_copies_and_freezes_named_outputs() -> None:
    outputs = {"result": REFERENCE}
    result = ProcedureExecutionResult(
        "execution",
        PROCEDURE,
        (REFERENCE,),
        outputs,
    )
    outputs.clear()

    assert result.outputs == {"result": REFERENCE}
    assert isinstance(result.outputs, MappingProxyType)


@pytest.mark.parametrize("identity", [object(), ""])
def test_execution_result_rejects_invalid_identity(identity: object) -> None:
    with pytest.raises((TypeError, ValueError), match="identity"):
        ProcedureExecutionResult(identity, PROCEDURE, ())  # type: ignore[arg-type]


def test_execution_result_rejects_invalid_procedure() -> None:
    with pytest.raises(TypeError, match="procedure"):
        ProcedureExecutionResult("execution", object(), ())  # type: ignore[arg-type]


def test_execution_result_rejects_invalid_inputs() -> None:
    with pytest.raises(TypeError, match="inputs"):
        ProcedureExecutionResult("execution", PROCEDURE, (object(),))  # type: ignore[arg-type]


def test_execution_result_rejects_mutable_input_collection() -> None:
    with pytest.raises(TypeError, match="tuple"):
        ProcedureExecutionResult(
            "execution",
            PROCEDURE,
            [REFERENCE],  # type: ignore[arg-type]
        )


def test_execution_result_rejects_non_mapping_outputs() -> None:
    with pytest.raises(TypeError, match="outputs"):
        ProcedureExecutionResult("execution", PROCEDURE, (), object())  # type: ignore[arg-type]


def test_execution_result_rejects_non_string_output_name() -> None:
    with pytest.raises(TypeError, match="names"):
        ProcedureExecutionResult(
            "execution",
            PROCEDURE,
            (),
            {1: REFERENCE},  # type: ignore[dict-item]
        )


def test_execution_result_rejects_empty_output_name() -> None:
    with pytest.raises(ValueError, match="names"):
        ProcedureExecutionResult("execution", PROCEDURE, (), {"": REFERENCE})


def test_execution_result_rejects_invalid_output_reference() -> None:
    with pytest.raises(TypeError, match="outputs"):
        ProcedureExecutionResult(
            "execution",
            PROCEDURE,
            (),
            {"result": object()},  # type: ignore[dict-item]
        )


def test_execution_result_rejects_invalid_lineage() -> None:
    with pytest.raises(TypeError, match="lineage"):
        ProcedureExecutionResult(
            "execution",
            PROCEDURE,
            (),
            lineage=object(),  # type: ignore[arg-type]
        )


def test_execution_result_defaults_to_empty_lineage() -> None:
    result = ProcedureExecutionResult("execution", None, ())

    assert result.lineage == ArtifactLineage()
