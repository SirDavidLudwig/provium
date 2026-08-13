from __future__ import annotations

from contextvars import Context, copy_context
from dataclasses import dataclass
from pathlib import Path

import pytest

from provium import (
    Artifact,
    ArtifactCatalog,
    ArtifactReader,
    ArtifactWriter,
    ConfigurationSnapshot,
    ExecutionContext,
    JsonValue,
    Procedure,
    current_execution,
    open_artifact,
)


@dataclass(frozen=True)
class Settings:
    value: int


class SettingsCodec:
    identifier = "settings-v1"

    def encode(self, config: Settings) -> JsonValue:
        return {"value": config.value}

    def decode(self, value: object) -> Settings:
        if not isinstance(value, dict):
            raise TypeError("expected object")
        return Settings(int(value["value"]))


class Reader(ArtifactReader):
    pass


class Writer(ArtifactWriter):
    pass


class Example(Artifact[Reader, Writer]):
    reader = Reader
    writer = Writer


def test_enters_and_exits_procedure_scope_and_exposes_active_execution() -> None:
    procedure = Procedure("example", "1")
    execution = procedure.execute()

    assert isinstance(execution, ExecutionContext)
    assert not execution.active
    assert current_execution() is None

    with execution as entered:
        assert entered is execution
        assert execution.active
        assert current_execution() is execution
        assert execution.procedure is procedure

    assert not execution.active
    assert current_execution() is None


def test_snapshots_procedure_config_when_context_is_created() -> None:
    procedure = Procedure[Settings]("configured", "2", SettingsCodec())

    execution = procedure.execute(config=Settings(42))

    assert execution.config_snapshot == ConfigurationSnapshot(
        "settings-v1", {"value": 42}
    )


def test_procedure_without_config_has_no_snapshot() -> None:
    execution = Procedure("plain", "1").execute()

    assert execution.config_snapshot is None


def test_generates_one_unique_execution_identity_per_context() -> None:
    procedure = Procedure("example", "1")

    first = procedure.execute()
    second = procedure.execute()

    assert first.identity
    assert second.identity
    assert first.identity != second.identity


def test_call_is_shorthand_for_execute() -> None:
    procedure = Procedure[Settings]("configured", "1", SettingsCodec())

    execution = procedure(config=Settings(42))

    assert execution.procedure is procedure
    assert execution.config_snapshot == ConfigurationSnapshot(
        "settings-v1", {"value": 42}
    )


def test_enters_procedure_directly_with_a_fresh_execution() -> None:
    procedure = Procedure("example", "1")

    with procedure as first:
        assert current_execution() is first
        assert first.procedure is procedure

    with procedure as second:
        assert current_execution() is second

    assert first.identity != second.identity
    assert current_execution() is None


def test_direct_procedure_exit_requires_a_matching_entry() -> None:
    with pytest.raises(RuntimeError, match="not directly active"):
        Procedure("example", "1").__exit__(None, None, None)


def test_context_cannot_be_entered_twice_or_reentered() -> None:
    execution = Procedure("example", "1").execute()

    with execution:
        with pytest.raises(RuntimeError, match="already"):
            execution.__enter__()

    with pytest.raises(RuntimeError, match="already"):
        execution.__enter__()


def test_rejects_nested_procedure_contexts_in_same_logical_context() -> None:
    outer = Procedure("outer", "1")
    inner = Procedure("inner", "1")

    with outer.execute():
        with pytest.raises(RuntimeError, match="nested"):
            with inner.execute():
                pass

        active_execution = current_execution()
        assert active_execution is not None
        assert active_execution.procedure is outer


def test_allows_independent_contextvars_contexts() -> None:
    procedure = Procedure("example", "1")
    first_logical_context = Context()
    second_logical_context = Context()

    def observe() -> tuple[str, bool]:
        with procedure.execute() as execution:
            return execution.identity, current_execution() is execution

    first_identity, first_active = first_logical_context.run(observe)
    second_identity, second_active = second_logical_context.run(observe)

    assert first_active and second_active
    assert first_identity != second_identity
    assert current_execution() is None


def test_copied_context_observes_same_active_execution() -> None:
    with Procedure("example", "1").execute() as execution:
        copied = copy_context()
        assert copied.run(current_execution) is execution


def test_artifact_io_without_active_context_is_rejected() -> None:
    with pytest.raises(RuntimeError, match="execution context"):
        Example.open("input.pa")
    with pytest.raises(RuntimeError, match="execution context"):
        Example.create("output.pa")
    with pytest.raises(RuntimeError, match="execution context"):
        open_artifact("input.pa")


def test_exit_requires_matching_active_context() -> None:
    execution = Procedure("example", "1").execute()

    with pytest.raises(RuntimeError, match="not active"):
        execution.__exit__(None, None, None)


def test_exceptional_exit_restores_context_state() -> None:
    with pytest.raises(LookupError, match="failure"):
        with Procedure("example", "1").execute() as execution:
            raise LookupError("failure")

    assert not execution.active
    assert current_execution() is None


def test_create_uses_class_path_for_unregistered_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("provium.procedure.discover_catalogs", ArtifactCatalog)
    path = tmp_path / "output.pa"

    with Procedure("example", "1").execute():
        writer = Example.create(path)

    assert writer.artifact_identifier == f"{Example.__module__}.{Example.__qualname__}"


def test_create_rejects_writer_factory_returning_wrong_object(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog = ArtifactCatalog()
    catalog.register("example.ExampleV1", Example)
    monkeypatch.setattr("provium.procedure.discover_catalogs", lambda: catalog)

    def invalid_writer(*args: object) -> object:
        return object()

    with (
        Procedure("example", "1").execute() as execution,
        pytest.raises(TypeError, match="ArtifactWriter"),
    ):
        execution.create_artifact(
            Example,
            "output.pa",
            invalid_writer,  # type: ignore[arg-type]
        )
