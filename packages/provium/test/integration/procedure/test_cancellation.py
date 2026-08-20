"""Integration tests for cooperative procedure cancellation."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

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
    CancellationToken,
    ProcedureCancelledError,
    ProcedureExecutor,
    session,
)


@pytest.fixture(autouse=True)
def reset_process_events():
    TransformProcedure.process_started_event = None
    TransformProcedure.process_continue_event = None
    yield
    TransformProcedure.process_started_event = None
    TransformProcedure.process_continue_event = None


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


def prepare_transform(tmp_path: Path):
    setup = tmp_path / "setup.provium"
    required = tmp_path / "required.provium"
    repeated = tmp_path / "repeated.provium"
    create_text(setup, "setup")
    create_text(required, "required")
    create_text(repeated, "repeated")
    prepared = ProcedureExecutor().prepare(
        TRANSFORM_PROCEDURE,
        setup_inputs={"setup": ArtifactReadBinding(TextArtifact, setup)},
    )
    inputs = {
        "required": ArtifactReadBinding(TextArtifact, required),
        "repeated": (ArtifactReadBinding(TextArtifact, repeated),),
    }
    return prepared, inputs


def output_bindings(tmp_path: Path, prefix: str) -> dict[str, object]:
    return {
        "transformed": ArtifactWriteBinding(
            TextArtifact,
            tmp_path / f"{prefix}-transformed.provium",
        ),
        "summary": ArtifactWriteBinding(
            TextArtifact,
            tmp_path / f"{prefix}-summary.provium",
        ),
    }


def test_mid_processing_cancellation_cleans_up_and_allows_reuse(
    tmp_path: Path,
) -> None:
    TransformProcedure.instances.clear()
    started = Event()
    release = Event()
    TransformProcedure.process_started_event = started
    TransformProcedure.process_continue_event = release
    prepared, inputs = prepare_transform(tmp_path)
    procedure = TransformProcedure.instances[-1]
    cancellation = CancellationToken()
    cancelled_outputs = output_bindings(tmp_path, "cancelled")

    with ThreadPoolExecutor(max_workers=1) as workers:
        future = workers.submit(
            prepared.execute,
            inputs=inputs,
            outputs=cancelled_outputs,
            cancellation=cancellation,
        )
        assert started.wait(timeout=5)
        cancellation.cancel()
        release.set()
        with pytest.raises(ProcedureCancelledError):
            future.result(timeout=5)

    process_directory = procedure.process_contexts[0].temporary_directory
    assert not process_directory.exists()
    assert all(not binding.path.exists() for binding in cancelled_outputs.values())
    assert not list(tmp_path.glob(".*.tmp"))
    assert not list(tmp_path.glob(".*.backup"))

    TransformProcedure.process_started_event = None
    TransformProcedure.process_continue_event = None
    successful_outputs = output_bindings(tmp_path, "successful")
    result = prepared.execute(inputs=inputs, outputs=successful_outputs)
    prepared.close()

    assert result.outputs.keys() == successful_outputs.keys()
    assert all(binding.path.exists() for binding in successful_outputs.values())
    assert read_text(successful_outputs["transformed"].path) == "setuprequiredrepeated"


def test_cancellation_before_execution_skips_process_hook(tmp_path: Path) -> None:
    TransformProcedure.instances.clear()
    prepared, inputs = prepare_transform(tmp_path)
    procedure = TransformProcedure.instances[-1]
    cancellation = CancellationToken()
    cancellation.cancel()
    outputs = output_bindings(tmp_path, "cancelled")

    with pytest.raises(ProcedureCancelledError):
        prepared.execute(
            inputs=inputs,
            outputs=outputs,
            cancellation=cancellation,
        )
    prepared.close()

    assert procedure.process_calls == 0
    assert procedure.process_contexts == []
    assert all(not binding.path.exists() for binding in outputs.values())
