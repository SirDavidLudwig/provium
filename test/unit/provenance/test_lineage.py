from __future__ import annotations

import pytest

from provium.provenance import (
    ArtifactLineage,
    ArtifactRecord,
    ArtifactReference,
    ProcedureExecutionRecord,
    ProcedureRecord,
)


def produce(
    execution_identity: str,
    output_identities: tuple[str, ...],
    *,
    inputs: tuple[ArtifactReference, ...] = (),
    input_lineages: tuple[ArtifactLineage, ...] = (),
    name: str = "produce",
) -> tuple[ArtifactLineage, tuple[ArtifactReference, ...]]:
    outputs = tuple(
        ArtifactReference(identity, "example.IntegerV1")
        for identity in output_identities
    )
    execution = ProcedureExecutionRecord(
        execution_identity,
        ProcedureRecord(name, "1"),
        inputs,
        outputs,
    )
    records = tuple(
        ArtifactRecord(output, f"digest-{output.identity}", execution_identity)
        for output in outputs
    )
    return ArtifactLineage.for_execution(execution, records, input_lineages), outputs


def test_build_lineage_for_zero_input_procedure() -> None:
    lineage, (root,) = produce("execution-root", ("root",))

    assert lineage.artifact(root) == ArtifactRecord(
        root, "digest-root", "execution-root"
    )
    assert lineage.producing_execution(root).identity == "execution-root"
    assert lineage.ancestry(root) == lineage


def test_extend_lineage_from_one_input_artifact() -> None:
    root_lineage, (root,) = produce("execution-root", ("root",))
    derived_lineage, (derived,) = produce(
        "execution-derived",
        ("derived",),
        inputs=(root,),
        input_lineages=(root_lineage,),
    )

    assert set(derived_lineage.artifacts) == {root.identity, derived.identity}
    assert set(derived_lineage.executions) == {"execution-root", "execution-derived"}
    assert derived_lineage.ancestry(derived) == derived_lineage


def test_merge_inputs_deduplicates_ancestors_and_preserves_branches() -> None:
    root_lineage, (root,) = produce("execution-root", ("root",))
    left_lineage, (left,) = produce(
        "execution-left",
        ("left",),
        inputs=(root,),
        input_lineages=(root_lineage,),
        name="left",
    )
    right_lineage, (right,) = produce(
        "execution-right",
        ("right",),
        inputs=(root,),
        input_lineages=(root_lineage,),
        name="right",
    )

    final_lineage, (final,) = produce(
        "execution-final",
        ("final",),
        inputs=(left, right),
        input_lineages=(left_lineage, right_lineage),
        name="join",
    )

    assert set(final_lineage.artifacts) == {"root", "left", "right", "final"}
    assert set(final_lineage.executions) == {
        "execution-root",
        "execution-left",
        "execution-right",
        "execution-final",
    }
    assert final_lineage.executions["execution-final"].inputs == (left, right)
    assert final_lineage.ancestry(final) == final_lineage


def test_multiple_outputs_share_one_execution() -> None:
    lineage, outputs = produce("execution-1", ("first", "second"))

    assert {lineage.producing_execution(output).identity for output in outputs} == {
        "execution-1"
    }


def test_equivalent_lineage_has_deterministic_serialization() -> None:
    first, _ = produce("execution-1", ("b", "a"))
    second, _ = produce("execution-1", ("a", "b"))

    assert first.to_json() == second.to_json()
    assert ArtifactLineage.from_json(first.to_json()) == first


def test_lineage_rejects_incomplete_or_conflicting_graphs() -> None:
    lineage, (root,) = produce("execution-root", ("root",))
    missing = ArtifactReference("missing", "example.IntegerV1")
    output = ArtifactReference("output", "example.IntegerV1")
    execution = ProcedureExecutionRecord(
        "execution-output", ProcedureRecord("next", "1"), (missing,), (output,)
    )
    output_record = ArtifactRecord(output, "digest-output", "execution-output")

    with pytest.raises(ValueError, match="input artifact"):
        ArtifactLineage.for_execution(execution, (output_record,), (lineage,))
    with pytest.raises(ValueError, match="output records"):
        ArtifactLineage.for_execution(execution, (), (lineage,))
    with pytest.raises(ValueError, match="producer"):
        ArtifactLineage.for_execution(
            execution,
            (ArtifactRecord(output, "digest-output", "different-execution"),),
            (lineage,),
        )

    conflicting_artifact = ArtifactLineage(
        artifacts={root.identity: ArtifactRecord(root, "different", "execution-root")},
        executions=lineage.executions,
    )
    with pytest.raises(ValueError, match="artifact conflict"):
        lineage.merge(conflicting_artifact)

    changed_execution = ProcedureExecutionRecord(
        "execution-root", ProcedureRecord("changed", "1"), outputs=(root,)
    )
    conflicting_execution = ArtifactLineage(
        lineage.artifacts, {changed_execution.identity: changed_execution}
    )
    with pytest.raises(ValueError, match="execution conflict"):
        lineage.merge(conflicting_execution)


def test_lineage_validation_and_lookup_failures_are_clear() -> None:
    lineage, (root,) = produce("execution-root", ("root",))
    unknown = ArtifactReference("unknown", "example.IntegerV1")

    with pytest.raises(KeyError):
        lineage.artifact(unknown)
    with pytest.raises(ValueError, match="does not match"):
        lineage.artifact(ArtifactReference(root.identity, "example.OtherV1"))
    with pytest.raises(ValueError, match="missing producer"):
        ArtifactLineage(lineage.artifacts, {})
    with pytest.raises(ValueError, match="output"):
        ArtifactLineage(
            lineage.artifacts,
            {
                "execution-root": ProcedureExecutionRecord(
                    "execution-root",
                    ProcedureRecord("produce", "1"),
                    outputs=(ArtifactReference("other", "example.IntegerV1"),),
                )
            },
        )

    record = lineage.artifacts[root.identity]
    execution = lineage.executions[record.producer_execution_identity]
    with pytest.raises(ValueError, match="artifact map key"):
        ArtifactLineage({"wrong-key": record}, lineage.executions)
    with pytest.raises(ValueError, match="execution map key"):
        ArtifactLineage({}, {"wrong-key": execution})
    with pytest.raises(ValueError, match="references missing artifact"):
        ArtifactLineage(
            lineage.artifacts,
            {
                execution.identity: ProcedureExecutionRecord(
                    execution.identity,
                    execution.procedure,
                    inputs=(ArtifactReference("absent", "example.IntegerV1"),),
                    outputs=execution.outputs,
                )
            },
        )


def test_build_rejects_reference_and_execution_identity_conflicts() -> None:
    lineage, (root,) = produce("execution-root", ("root",))
    mismatched_root = ArtifactReference(root.identity, "example.OtherV1")
    output = ArtifactReference("output", "example.IntegerV1")
    mismatched_input_execution = ProcedureExecutionRecord(
        "execution-next", ProcedureRecord("next", "1"), (mismatched_root,), (output,)
    )
    with pytest.raises(ValueError, match="input artifact"):
        ArtifactLineage.for_execution(
            mismatched_input_execution,
            (ArtifactRecord(output, "digest-output", "execution-next"),),
            (lineage,),
        )

    reused_identity_execution = ProcedureExecutionRecord(
        "execution-root", ProcedureRecord("different", "1"), (root,), (output,)
    )
    with pytest.raises(ValueError, match="execution conflict"):
        ArtifactLineage.for_execution(
            reused_identity_execution,
            (ArtifactRecord(output, "digest-output", "execution-root"),),
            (lineage,),
        )


def test_lineage_deserialization_rejects_invalid_shape() -> None:
    with pytest.raises(ValueError, match="lineage"):
        ArtifactLineage.from_dict({"artifacts": []})
    with pytest.raises(TypeError, match="lineage"):
        ArtifactLineage.from_dict({"artifacts": {}, "executions": []})
    with pytest.raises(TypeError, match="lineage"):
        ArtifactLineage.from_dict({"artifacts": [], "executions": {}})
