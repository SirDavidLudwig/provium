from __future__ import annotations

from typing import assert_type

from provium import (
    Artifact,
    ArtifactReader,
    ArtifactWriter,
    ExecutionContext,
    Procedure,
    ProcedureInstance,
)


class IntegerReader(ArtifactReader):
    pass


class IntegerWriter(ArtifactWriter):
    pass


class Integer(Artifact[IntegerReader, IntegerWriter]):
    reader = IntegerReader
    writer = IntegerWriter


def static_type_contract() -> None:
    assert_type(Integer.open("input.pa"), IntegerReader)
    assert_type(Integer.create("output.pa"), IntegerWriter)


class Settings:
    pass


class State:
    pass


def setup(_: Settings) -> State:
    return State()


def procedure_static_type_contract(settings: Settings) -> None:
    procedure: Procedure[Settings, State] = Procedure("typed", "1", setup=setup)
    instance = assert_type(
        procedure(config=settings), ProcedureInstance[Settings, State]
    )
    execution = assert_type(instance.__enter__(), ExecutionContext[Settings, State])
    assert_type(instance.state, State)
    assert_type(execution.state, State)
