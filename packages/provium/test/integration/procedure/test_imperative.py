"""Integration tests for imperative procedure execution."""

from __future__ import annotations

from pathlib import Path

import pytest
from support.provium_test_pipeline.artifacts import TextArtifact
from support.provium_test_pipeline.contracts import SOURCE_PROCEDURE

from provium import (
    ArtifactHeader,
    ArtifactReference,
    ImperativeProcedure,
    ProcedureExecutor,
    ProcedureRecord,
    current_session,
    session,
)


def create_text(path: Path, text: str) -> ArtifactReference:
    result = ProcedureExecutor().execute(
        SOURCE_PROCEDURE,
        configuration_layers=({"text": text},),
        inputs={},
        outputs={"value": TextArtifact.bind_write(path)},
    )
    return result.outputs["value"]


def read_text(path: Path) -> tuple[str, ArtifactHeader]:
    with session():
        with TextArtifact.bind_read(path).open() as reader:
            return reader.read_text(), reader.metadata


def test_imperative_reads_one_source_and_writes_one_provenanced_output(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.provium"
    destination = tmp_path / "destination.provium"
    source_reference = create_text(source, "source")
    input_binding = TextArtifact.bind_read(source)
    output_binding = TextArtifact.bind_write(destination)

    with ImperativeProcedure("test.ImperativeUpperV1", "contract-digest").execute(
        inputs=(input_binding,),
        outputs={"result": output_binding},
    ) as execution:
        with input_binding.open() as reader:
            with output_binding.open() as writer:
                writer.write_text(reader.read_text().upper())

    result = execution.result
    assert result is not None
    assert result.procedure == ProcedureRecord(
        "test.ImperativeUpperV1",
        "contract-digest",
    )
    assert result.inputs == (source_reference,)
    assert tuple(result.outputs) == ("result",)
    body, header = read_text(destination)
    assert body == "SOURCE"
    assert header.lineage == result.lineage
    stored_execution = header.lineage.executions[result.identity]
    assert stored_execution.inputs == result.inputs
    assert stored_execution.outputs == tuple(result.outputs.values())


def test_imperative_preserves_input_and_output_order_inside_outer_session(
    tmp_path: Path,
) -> None:
    source_paths = [tmp_path / f"source-{index}.provium" for index in range(3)]
    source_references = tuple(
        create_text(path, text)
        for path, text in zip(source_paths, ("A", "B", "C"), strict=True)
    )
    input_bindings = tuple(TextArtifact.bind_read(path) for path in source_paths)
    first = TextArtifact.bind_write(tmp_path / "first.provium")
    second = TextArtifact.bind_write(tmp_path / "second.provium")
    outer = session()

    with outer:
        with ImperativeProcedure("test.ImperativeManyV1", "digest").execute(
            inputs=input_bindings,
            outputs={"first": first, "second": second},
        ) as execution:
            values = []
            for binding in input_bindings:
                with binding.open() as reader:
                    values.append(reader.read_text())
            with first.open() as writer:
                writer.write_text("".join(values))
            with second.open() as writer:
                writer.write_text("|".join(reversed(values)))
        assert current_session() is outer

    result = execution.result
    assert result is not None
    assert result.inputs == source_references
    assert tuple(result.outputs) == ("first", "second")
    first_body, first_header = read_text(first.path)
    second_body, second_header = read_text(second.path)
    assert first_body == "ABC"
    assert second_body == "C|B|A"
    assert first_header.lineage == second_header.lineage == result.lineage


def test_imperative_read_only_execution_returns_complete_input_lineage(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.provium"
    source_reference = create_text(source, "read-only")
    binding = TextArtifact.bind_read(source)

    with ImperativeProcedure("test.ImperativeReadV1", "digest").execute(
        inputs=(binding,)
    ) as execution:
        with binding.open() as reader:
            assert reader.read_text() == "read-only"

    assert execution.result is not None
    assert execution.result.inputs == (source_reference,)
    assert execution.result.outputs == {}
    assert execution.result.lineage.artifact(source_reference).reference == (
        source_reference
    )


def test_imperative_failure_is_transactional_and_execution_is_single_use(
    tmp_path: Path,
) -> None:
    existing = tmp_path / "existing.provium"
    new = tmp_path / "new.provium"
    undeclared_path = tmp_path / "undeclared.provium"
    existing.write_bytes(b"original")
    declared = TextArtifact.bind_write(existing)
    declared_new = TextArtifact.bind_write(new)
    undeclared = TextArtifact.bind_write(undeclared_path)
    execution = ImperativeProcedure("test.ImperativeFailV1", "digest").execute(
        outputs={"result": declared, "secondary": declared_new}
    )

    with pytest.raises(ValueError, match="processing failed"):
        with execution:
            with declared.open() as writer:
                writer.write_text("replacement")
            with declared_new.open() as writer:
                writer.write_text("partial new output")
            with pytest.raises(RuntimeError, match="not declared"):
                undeclared.open()
            raise ValueError("processing failed")

    assert execution.result is None
    assert existing.read_bytes() == b"original"
    assert not new.exists()
    assert not undeclared_path.exists()
    assert not list(tmp_path.glob(".*.tmp"))
    with pytest.raises(RuntimeError, match="already been entered"):
        execution.__enter__()
