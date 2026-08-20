"""Integration tests for reusable prepared procedure state."""

from __future__ import annotations

from pathlib import Path

import pytest
from support.provium_test_pipeline.artifacts import TextArtifact
from support.provium_test_pipeline.contracts import (
    SOURCE_PROCEDURE,
    TRANSFORM_PROCEDURE,
)
from support.provium_test_pipeline.procedures import TransformProcedure

from provium import (
    ArtifactReadBinding,
    ArtifactWriteBinding,
    ProcedureExecutor,
    session,
)


def create_text(path: Path, text: str) -> None:
    ProcedureExecutor().execute(
        SOURCE_PROCEDURE,
        configuration_layers=({"text": text},),
        inputs={},
        outputs={"value": ArtifactWriteBinding(TextArtifact, path)},
    )


def read_text(path: Path) -> str:
    with session():
        with ArtifactReadBinding(TextArtifact, path).open() as reader:
            return reader.read_text()


def test_prepared_pipeline_reuses_setup_and_isolates_each_invocation(
    tmp_path: Path,
) -> None:
    TransformProcedure.instances.clear()
    setup_path = tmp_path / "setup.provium"
    create_text(setup_path, "setup-")
    invocation_paths: list[tuple[Path, Path]] = []
    for index in range(2):
        required = tmp_path / f"required-{index}.provium"
        repeated = tmp_path / f"repeated-{index}.provium"
        create_text(required, f"required-{index}-")
        create_text(repeated, f"repeated-{index}")
        invocation_paths.append((required, repeated))

    prepared = ProcedureExecutor().prepare(
        TRANSFORM_PROCEDURE,
        configuration_layers=({"prefix": "["}, {"suffix": "]"}),
        setup_inputs={"setup": ArtifactReadBinding(TextArtifact, setup_path)},
    )
    procedure = TransformProcedure.instances[-1]
    setup_temporary_directory = procedure.setup_context.temporary_directory
    results = []
    output_paths = []

    for index, (required, repeated) in enumerate(invocation_paths):
        transformed = tmp_path / f"transformed-{index}.provium"
        summary = tmp_path / f"summary-{index}.provium"
        result = prepared.execute(
            inputs={
                "required": ArtifactReadBinding(TextArtifact, required),
                "repeated": (ArtifactReadBinding(TextArtifact, repeated),),
            },
            outputs={
                "transformed": ArtifactWriteBinding(TextArtifact, transformed),
                "summary": ArtifactWriteBinding(TextArtifact, summary),
            },
        )
        results.append(result)
        output_paths.append(transformed)

    process_temporary_directories = [
        context.temporary_directory for context in procedure.process_contexts
    ]
    prepared.close()

    assert procedure.setup_calls == 1
    assert procedure.process_calls == 2
    assert procedure.close_calls == 1
    assert procedure.setup_configuration is prepared.configuration
    assert procedure.process_configurations == [
        prepared.configuration,
        prepared.configuration,
    ]
    assert procedure.setup_temporary_directory_existed is True
    assert procedure.process_temporary_directories_existed == [True, True]
    assert procedure.setup_temporary_directory_existed_during_close is True
    assert not setup_temporary_directory.exists()
    assert len({id(context) for context in procedure.process_contexts}) == 2
    assert len(set(process_temporary_directories)) == 2
    assert all(not path.exists() for path in process_temporary_directories)
    assert results[0].identity != results[1].identity
    assert [read_text(path) for path in output_paths] == [
        "[setup-required-0-repeated-0]",
        "[setup-required-1-repeated-1]",
    ]

    setup_identity = results[0].inputs[0].identity
    invocation_input_identities = [
        {reference.identity for reference in result.inputs} for result in results
    ]
    assert invocation_input_identities[0] & invocation_input_identities[1] == {
        setup_identity
    }
    for result in results:
        execution = result.lineage.executions[result.identity]
        assert execution.inputs[0].identity == setup_identity
        assert execution.inputs[1:] == result.inputs[1:]

    with pytest.raises(RuntimeError, match="prepared procedure is closed"):
        prepared.execute(inputs={}, outputs={})
