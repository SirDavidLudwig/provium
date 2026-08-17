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
    ProcedureInstance,
    current_execution,
    open_artifact,
    session,
)
from provium.procedure import _PersistentSession


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


def test_call_creates_a_lazy_configured_procedure_instance() -> None:
    procedure = Procedure[Settings]("configured", "1", SettingsCodec())

    instance = procedure(config=Settings(42))

    assert isinstance(instance, ProcedureInstance)
    assert instance.procedure is procedure
    assert instance.config_snapshot == ConfigurationSnapshot(
        "settings-v1", {"value": 42}
    )
    with pytest.raises(RuntimeError, match="has not run"):
        instance.state

    assert Procedure[Settings, None]("typed", "1").name == "typed"


def test_instance_without_setup_repeats_with_fresh_executions() -> None:
    instance = Procedure("plain", "1")()

    with session():
        with instance as first:
            assert first.state is None
        with instance as second:
            assert second.state is None

    assert first.identity != second.identity


def test_instance_rejects_invalid_lifecycle_operations() -> None:
    instance = Procedure("plain", "1")()
    unused = Procedure("unused", "1")()
    unused.close()
    with pytest.raises(RuntimeError, match="closed session"):
        unused.__enter__()

    with pytest.raises(RuntimeError, match="not executing"):
        instance.__exit__(None, None, None)

    with session():
        nested = Procedure("nested", "1")()
        with Procedure("outer", "1").execute():
            with pytest.raises(RuntimeError, match="nested"):
                nested.__enter__()
        with instance:
            with pytest.raises(RuntimeError, match="already executing"):
                instance.__enter__()
            with pytest.raises(RuntimeError, match="cannot close"):
                instance.close()

    instance.close()
    with pytest.raises(RuntimeError, match="closed session"):
        instance.__enter__()


def test_instance_cannot_move_between_active_logical_sessions() -> None:
    instance = Procedure("plain", "1")()
    owner = session()
    owner.__enter__()
    with instance:
        pass

    def enter_in_another_session() -> None:
        with session(), pytest.raises(RuntimeError, match="different session"):
            instance.__enter__()

    Context().run(enter_in_another_session)
    owner.__exit__(None, None, None)


def test_failed_setup_closes_the_instance() -> None:
    def fail(_: None) -> object:
        raise LookupError("setup failure")

    instance = Procedure("broken", "1", setup=fail)()
    with session():
        with pytest.raises(LookupError, match="setup failure"):
            instance.__enter__()
        with pytest.raises(RuntimeError, match="closed session"):
            instance.__enter__()


def test_persistent_session_defensive_lifecycle() -> None:
    owner = session()
    persistent = _PersistentSession(owner=owner)

    with pytest.raises(RuntimeError, match="owning session"):
        persistent.__enter__()

    with owner:
        persistent.__enter__()
        with pytest.raises(RuntimeError, match="already active"):
            persistent.__enter__()
        persistent.__exit__(None, None, None)
        with pytest.raises(RuntimeError, match="not active"):
            persistent.__exit__(None, None, None)
        persistent.close()
        persistent.close()
        with pytest.raises(RuntimeError, match="closed"):
            persistent.__enter__()


def test_persistent_session_reports_reader_cleanup_failure() -> None:
    class BrokenBody:
        def close(self) -> None:
            raise OSError("body cleanup failure")

    class BrokenReader:
        _body = BrokenBody()

        def close(self) -> None:
            raise OSError("reader cleanup failure")

    with session() as owner:
        persistent = _PersistentSession(owner=owner)
        persistent.__enter__()
        persistent._readers.extend((BrokenReader(), BrokenReader()))  # type: ignore[arg-type]
        with pytest.raises(OSError, match="reader cleanup failure"):
            persistent.close()

        assert persistent.closed
        assert not persistent.active


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
