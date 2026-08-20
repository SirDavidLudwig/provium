"""Integration tests for transactional procedure failure behavior."""

from __future__ import annotations

from pathlib import Path

import pytest
from support.provium_test_pipeline.artifacts import TextArtifact
from support.provium_test_pipeline.contracts import (
    FAILING_PROCEDURE,
    SOURCE_PROCEDURE,
    TRANSFORM_PROCEDURE,
)
from support.provium_test_pipeline.procedures import FailingProcedure

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


def assert_no_transaction_files(directory: Path) -> None:
    assert not list(directory.glob(".*.tmp"))
    assert not list(directory.glob(".*.backup"))


def read_text(path: Path) -> str:
    with session():
        with ArtifactReadBinding(TextArtifact, path).open() as reader:
            return reader.read_text()


def test_processing_failure_removes_partial_new_output(tmp_path: Path) -> None:
    source = tmp_path / "source.provium"
    destination = tmp_path / "new.provium"
    create_text(source, "source")

    with pytest.raises(RuntimeError, match="deliberate integration test failure"):
        ProcedureExecutor().execute(
            FAILING_PROCEDURE,
            inputs={"source": ArtifactReadBinding(TextArtifact, source)},
            outputs={"result": ArtifactWriteBinding(TextArtifact, destination)},
        )

    assert not destination.exists()
    assert_no_transaction_files(tmp_path)


def test_prepared_procedure_is_reusable_after_multi_output_failure(
    tmp_path: Path,
) -> None:
    FailingProcedure.instances.clear()
    source = tmp_path / "source.provium"
    existing = tmp_path / "existing.provium"
    new = tmp_path / "new.provium"
    create_text(source, "source")
    existing.write_bytes(b"original")
    prepared = ProcedureExecutor().prepare(FAILING_PROCEDURE)
    procedure = FailingProcedure.instances[-1]

    with pytest.raises(RuntimeError, match="deliberate integration test failure"):
        prepared.execute(
            inputs={"source": ArtifactReadBinding(TextArtifact, source)},
            outputs={
                "result": ArtifactWriteBinding(TextArtifact, existing),
                "secondary": ArtifactWriteBinding(TextArtifact, new),
            },
        )

    assert existing.read_bytes() == b"original"
    assert not new.exists()
    assert_no_transaction_files(tmp_path)

    procedure.should_fail = False
    successful = tmp_path / "successful.provium"
    result = prepared.execute(
        inputs={"source": ArtifactReadBinding(TextArtifact, source)},
        outputs={"result": ArtifactWriteBinding(TextArtifact, successful)},
    )
    prepared.close()

    assert result.outputs["result"].identity
    assert read_text(successful) == "sou"
    assert_no_transaction_files(tmp_path)


def test_multi_output_publication_failure_restores_all_destinations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = tmp_path / "setup.provium"
    required = tmp_path / "required.provium"
    repeated = tmp_path / "repeated.provium"
    first = tmp_path / "first.provium"
    second = tmp_path / "second.provium"
    create_text(setup, "setup")
    create_text(required, "required")
    create_text(repeated, "repeated")
    first.write_bytes(b"original-first")
    second.write_bytes(b"original-second")
    original_replace = Path.replace

    def fail_second_publish(source: Path, destination: Path) -> Path:
        if source.name.endswith(".tmp") and destination == second:
            raise OSError("second publication failed")
        return original_replace(source, destination)

    monkeypatch.setattr(Path, "replace", fail_second_publish)

    with pytest.raises(OSError, match="second publication failed"):
        ProcedureExecutor().execute(
            TRANSFORM_PROCEDURE,
            setup_inputs={"setup": ArtifactReadBinding(TextArtifact, setup)},
            inputs={
                "required": ArtifactReadBinding(TextArtifact, required),
                "repeated": (ArtifactReadBinding(TextArtifact, repeated),),
            },
            outputs={
                "transformed": ArtifactWriteBinding(TextArtifact, first),
                "summary": ArtifactWriteBinding(TextArtifact, second),
            },
        )

    assert first.read_bytes() == b"original-first"
    assert second.read_bytes() == b"original-second"
    assert_no_transaction_files(tmp_path)


def test_publication_error_is_preserved_when_restoration_also_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = tmp_path / "setup.provium"
    required = tmp_path / "required.provium"
    repeated = tmp_path / "repeated.provium"
    first = tmp_path / "first.provium"
    second = tmp_path / "second.provium"
    for path, text in (
        (setup, "setup"),
        (required, "required"),
        (repeated, "repeated"),
    ):
        create_text(path, text)
    first.write_bytes(b"original-first")
    second.write_bytes(b"original-second")
    original_replace = Path.replace

    def fail_publication_and_restore(source: Path, destination: Path) -> Path:
        if source.name.endswith(".tmp") and destination == second:
            raise OSError("publication failed")
        if source.name.endswith(".backup"):
            raise RuntimeError("restoration failed")
        return original_replace(source, destination)

    monkeypatch.setattr(Path, "replace", fail_publication_and_restore)

    with pytest.raises(OSError, match="publication failed") as caught:
        ProcedureExecutor().execute(
            TRANSFORM_PROCEDURE,
            setup_inputs={"setup": ArtifactReadBinding(TextArtifact, setup)},
            inputs={
                "required": ArtifactReadBinding(TextArtifact, required),
                "repeated": (ArtifactReadBinding(TextArtifact, repeated),),
            },
            outputs={
                "transformed": ArtifactWriteBinding(TextArtifact, first),
                "summary": ArtifactWriteBinding(TextArtifact, second),
            },
        )

    assert isinstance(caught.value.__cause__, RuntimeError)
    assert str(caught.value.__cause__) == "restoration failed"
