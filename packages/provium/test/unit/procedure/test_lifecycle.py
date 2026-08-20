"""Tests for the base stateful procedure lifecycle interface."""

from pathlib import Path

import pytest

from provium import (
    CancellationToken,
    Procedure,
    ProcedureConfig,
    ProcedureInputs,
    ProcedureOutputs,
    ProcedureProcessContext,
    ProcedureSetupContext,
)


def test_cancellation_token_is_thread_safe_and_idempotent() -> None:
    token = CancellationToken()

    assert token.cancelled is False
    token.raise_if_cancelled()
    token.cancel()
    token.cancel()

    assert token.cancelled is True
    with pytest.raises(RuntimeError, match="procedure execution was cancelled"):
        token.raise_if_cancelled()


def test_lifecycle_contexts_expose_cancellation_and_temporary_directory(
    tmp_path: Path,
) -> None:
    token = CancellationToken()

    setup = ProcedureSetupContext(token, tmp_path)
    process = ProcedureProcessContext(token, tmp_path)

    assert setup.cancellation is token
    assert setup.temporary_directory == tmp_path
    assert process.cancellation is token
    assert process.temporary_directory == tmp_path


class Config(ProcedureConfig):
    pass


class SetupInputs(ProcedureInputs):
    pass


class Inputs(ProcedureInputs):
    pass


class Outputs(ProcedureOutputs):
    pass


def test_process_is_required_for_a_concrete_procedure() -> None:
    class IncompleteProcedure(Procedure[Config, SetupInputs, Inputs, Outputs]):
        pass

    with pytest.raises(TypeError, match="abstract method 'process'"):
        IncompleteProcedure()


def test_default_setup_and_close_hooks_are_no_ops() -> None:
    class ConcreteProcedure(Procedure[Config, SetupInputs, Inputs, Outputs]):
        def process(
            self,
            context: ProcedureProcessContext,
            configuration: Config,
            inputs: Inputs,
            outputs: Outputs,
        ) -> None:
            pass

    procedure = ConcreteProcedure()

    assert (
        procedure.setup(
            ProcedureSetupContext(),
            Config(),
            SetupInputs._from_bindings({}),
        )
        is None
    )
    assert procedure.close() is None


def test_process_receives_the_declared_runtime_types() -> None:
    calls: list[tuple[object, ...]] = []

    class ConcreteProcedure(Procedure[Config, SetupInputs, Inputs, Outputs]):
        def process(
            self,
            context: ProcedureProcessContext,
            configuration: Config,
            inputs: Inputs,
            outputs: Outputs,
        ) -> None:
            calls.append((context, configuration, inputs, outputs))

    procedure = ConcreteProcedure()
    context = ProcedureProcessContext()
    configuration = Config()
    inputs = Inputs._from_bindings({})
    outputs = Outputs._from_bindings({})

    procedure.process(context, configuration, inputs, outputs)

    assert calls == [(context, configuration, inputs, outputs)]
