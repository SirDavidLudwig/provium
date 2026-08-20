"""Tests for normalized artifact lineage graphs."""

import pytest

from provium import (
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
) -> tuple[ArtifactLineage, tuple[ArtifactReference, ...]]:
    outputs = tuple(
        ArtifactReference(identity, "example.ImageV1") for identity in output_identities
    )
    execution = ProcedureExecutionRecord(
        execution_identity,
        ProcedureRecord("example.ProduceV1", "contract-digest"),
        inputs,
        outputs,
    )
    records = tuple(
        ArtifactRecord(output, f"digest-{output.identity}", execution_identity)
        for output in outputs
    )
    return ArtifactLineage.for_execution(execution, records, input_lineages), outputs


def test_lineage_builds_merges_and_extracts_ancestry() -> None:
    root_lineage, (root,) = produce("execution-root", ("root",))
    left_lineage, (left,) = produce(
        "execution-left",
        ("left",),
        inputs=(root,),
        input_lineages=(root_lineage,),
    )
    right_lineage, (right,) = produce(
        "execution-right",
        ("right",),
        inputs=(root,),
        input_lineages=(root_lineage,),
    )
    final_lineage, (final,) = produce(
        "execution-final",
        ("final",),
        inputs=(right, left),
        input_lineages=(left_lineage, right_lineage),
    )

    assert set(final_lineage.artifacts) == {"root", "left", "right", "final"}
    assert set(final_lineage.executions) == {
        "execution-root",
        "execution-left",
        "execution-right",
        "execution-final",
    }
    assert final_lineage.artifact(final).body_digest == "digest-final"
    assert final_lineage.producing_execution(final).identity == "execution-final"
    assert final_lineage.ancestry(final) == final_lineage

    with pytest.raises(TypeError):
        final_lineage.artifacts["other"] = final_lineage.artifacts["root"]  # type: ignore[index]


def test_lineage_serialization_is_deterministic_and_round_trips() -> None:
    first, _ = produce("execution-1", ("second", "first"))
    second, _ = produce("execution-1", ("first", "second"))

    assert first.to_json() == second.to_json()
    assert ArtifactLineage.from_json(first.to_json()) == first


def test_lineage_rejects_incomplete_graphs_and_invalid_map_keys() -> None:
    lineage, (root,) = produce("execution-root", ("root",))
    record = lineage.artifacts[root.identity]
    execution = lineage.executions[record.producer_execution_identity]

    with pytest.raises(ValueError, match="artifact map key"):
        ArtifactLineage({"wrong": record}, lineage.executions)
    with pytest.raises(ValueError, match="execution map key"):
        ArtifactLineage({}, {"wrong": execution})
    with pytest.raises(ValueError, match="missing producer"):
        ArtifactLineage(lineage.artifacts, {})
    with pytest.raises(TypeError, match="artifact map values"):
        ArtifactLineage({"invalid": object()}, {})  # type: ignore[dict-item]
    with pytest.raises(TypeError, match="execution map values"):
        ArtifactLineage({}, {"invalid": object()})  # type: ignore[dict-item]

    different_output = ArtifactReference("different", "example.ImageV1")
    with pytest.raises(ValueError, match="not an output"):
        ArtifactLineage(
            lineage.artifacts,
            {
                execution.identity: ProcedureExecutionRecord(
                    execution.identity,
                    execution.procedure,
                    outputs=(different_output,),
                )
            },
        )

    absent = ArtifactReference("absent", "example.ImageV1")
    with pytest.raises(ValueError, match="references missing artifact"):
        ArtifactLineage(
            lineage.artifacts,
            {
                execution.identity: ProcedureExecutionRecord(
                    execution.identity,
                    execution.procedure,
                    inputs=(absent,),
                    outputs=execution.outputs,
                )
            },
        )

    derived_lineage, (derived,) = produce(
        "execution-derived",
        ("derived",),
        inputs=(root,),
        input_lineages=(lineage,),
    )
    derived_execution = derived_lineage.producing_execution(derived)
    mismatched_reference = ArtifactReference(root.identity, "example.OtherV1")
    with pytest.raises(ValueError, match="reference does not match artifact"):
        ArtifactLineage(
            derived_lineage.artifacts,
            {
                **derived_lineage.executions,
                derived_execution.identity: ProcedureExecutionRecord(
                    derived_execution.identity,
                    derived_execution.procedure,
                    inputs=(mismatched_reference,),
                    outputs=derived_execution.outputs,
                ),
            },
        )


def test_for_execution_rejects_incomplete_or_conflicting_edges() -> None:
    lineage, (root,) = produce("execution-root", ("root",))
    missing = ArtifactReference("missing", "example.ImageV1")
    output = ArtifactReference("output", "example.ImageV1")
    execution = ProcedureExecutionRecord(
        "execution-next",
        ProcedureRecord("example.NextV1", "contract-digest"),
        inputs=(missing,),
        outputs=(output,),
    )
    record = ArtifactRecord(output, "digest-output", execution.identity)

    with pytest.raises(ValueError, match="input artifact"):
        ArtifactLineage.for_execution(execution, (record,), (lineage,))
    with pytest.raises(ValueError, match="output records"):
        ArtifactLineage.for_execution(execution, (), (lineage,))
    with pytest.raises(ValueError, match="producer"):
        ArtifactLineage.for_execution(
            execution,
            (ArtifactRecord(output, "digest-output", "other-execution"),),
            (lineage,),
        )

    reused_execution = ProcedureExecutionRecord(
        "execution-root",
        ProcedureRecord("example.ChangedV1", "contract-digest"),
        inputs=(root,),
        outputs=(output,),
    )
    with pytest.raises(ValueError, match="execution conflict"):
        ArtifactLineage.for_execution(
            reused_execution,
            (ArtifactRecord(output, "digest-output", "execution-root"),),
            (lineage,),
        )


def test_merge_and_lookup_reject_identity_conflicts() -> None:
    lineage, (root,) = produce("execution-root", ("root",))
    record = lineage.artifacts[root.identity]
    execution = lineage.executions[record.producer_execution_identity]

    conflicting_artifact = ArtifactLineage(
        {root.identity: ArtifactRecord(root, "different", execution.identity)},
        lineage.executions,
    )
    with pytest.raises(ValueError, match="artifact conflict"):
        lineage.merge(conflicting_artifact)

    changed_execution = ProcedureExecutionRecord(
        execution.identity,
        ProcedureRecord("example.ChangedV1", "contract-digest"),
        outputs=(root,),
    )
    conflicting_execution = ArtifactLineage(
        lineage.artifacts,
        {changed_execution.identity: changed_execution},
    )
    with pytest.raises(ValueError, match="execution conflict"):
        lineage.merge(conflicting_execution)

    with pytest.raises(KeyError):
        lineage.artifact(ArtifactReference("unknown", "example.ImageV1"))
    with pytest.raises(ValueError, match="does not match"):
        lineage.artifact(ArtifactReference(root.identity, "example.OtherV1"))


def test_lineage_rejects_producer_cycles() -> None:
    first = ArtifactReference("first", "example.ImageV1")
    second = ArtifactReference("second", "example.ImageV1")
    procedure = ProcedureRecord("example.CycleV1", "contract-digest")
    first_execution = ProcedureExecutionRecord(
        "execution-first",
        procedure,
        inputs=(second,),
        outputs=(first,),
    )
    second_execution = ProcedureExecutionRecord(
        "execution-second",
        procedure,
        inputs=(first,),
        outputs=(second,),
    )

    with pytest.raises(ValueError, match="cycle"):
        ArtifactLineage(
            {
                first.identity: ArtifactRecord(
                    first,
                    "digest-first",
                    first_execution.identity,
                ),
                second.identity: ArtifactRecord(
                    second,
                    "digest-second",
                    second_execution.identity,
                ),
            },
            {
                first_execution.identity: first_execution,
                second_execution.identity: second_execution,
            },
        )


def test_lineage_deserialization_rejects_invalid_shapes() -> None:
    with pytest.raises(ValueError, match="lineage"):
        ArtifactLineage.from_dict({"artifacts": []})
    with pytest.raises(TypeError, match="lineage"):
        ArtifactLineage.from_dict({"artifacts": {}, "executions": []})
    with pytest.raises(TypeError, match="lineage"):
        ArtifactLineage.from_dict({"artifacts": [], "executions": {}})


@pytest.mark.parametrize("collection", ["artifacts", "executions"])
def test_lineage_deserialization_rejects_duplicate_entries(collection: str) -> None:
    lineage, _ = produce("execution-root", ("root",))
    encoded = lineage.to_dict()
    encoded[collection].append(encoded[collection][0])

    with pytest.raises(ValueError, match=rf"duplicate {collection[:-1]}"):
        ArtifactLineage.from_dict(encoded)
