"""Tests for reusable prepared procedure instances."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from provium import (
    PreparedProcedure,
    Procedure,
    ProcedureConfig,
    ProcedureInputs,
    ProcedureOutputs,
    ProcedureProcessContext,
    ProcedureSetupContext,
)


class Config(ProcedureConfig):
    increment: int


class SetupInputs(ProcedureInputs):
    pass


class Inputs(ProcedureInputs):
    pass


class Outputs(ProcedureOutputs):
    pass


class CounterProcedure(Procedure[Config, SetupInputs, Inputs, Outputs]):
    def __init__(self) -> None:
        self.total = 0
        self.setup_calls = 0
        self.process_contexts: list[ProcedureProcessContext] = []
        self.configurations: list[Config] = []
        self.close_calls = 0

    def setup(
        self,
        context: ProcedureSetupContext,
        configuration: Config,
        inputs: SetupInputs,
    ) -> None:
        self.setup_calls += 1
        self.total = configuration.increment
        self.configurations.append(configuration)

    def process(
        self,
        context: ProcedureProcessContext,
        configuration: Config,
        inputs: Inputs,
        outputs: Outputs,
    ) -> None:
        self.process_contexts.append(context)
        self.configurations.append(configuration)
        self.total += configuration.increment

    def close(self) -> None:
        self.close_calls += 1


def prepare(
    procedure: CounterProcedure | None = None,
) -> tuple[PreparedProcedure[Config, Inputs, Outputs], CounterProcedure, Config]:
    implementation = CounterProcedure() if procedure is None else procedure
    configuration = Config(increment=2)
    prepared = PreparedProcedure(
        implementation,
        configuration,
        SetupInputs._from_bindings({}),
    )
    return prepared, implementation, configuration


def test_prepared_procedure_retains_state_across_sequential_executions() -> None:
    prepared, procedure, configuration = prepare()
    inputs = Inputs._from_bindings({})
    outputs = Outputs._from_bindings({})

    assert prepared.configuration is configuration
    assert procedure.setup_calls == 1

    assert prepared.execute(inputs=inputs, outputs=outputs) is None
    assert prepared.execute(inputs=inputs, outputs=outputs) is None

    assert procedure.total == 6
    assert procedure.configurations == [configuration, configuration, configuration]
    assert len(procedure.process_contexts) == 2
    assert procedure.process_contexts[0] is not procedure.process_contexts[1]


def test_prepared_procedure_closes_its_implementation_exactly_once() -> None:
    prepared, procedure, _ = prepare()

    assert prepared.close() is None
    assert prepared.close() is None
    assert procedure.close_calls == 1

    with pytest.raises(RuntimeError, match="prepared procedure is closed"):
        prepared.execute(
            inputs=Inputs._from_bindings({}),
            outputs=Outputs._from_bindings({}),
        )


def test_processing_failure_does_not_prevent_a_later_execution() -> None:
    class FailingOnceProcedure(CounterProcedure):
        def __init__(self) -> None:
            super().__init__()
            self.fail = True

        def process(
            self,
            context: ProcedureProcessContext,
            configuration: Config,
            inputs: Inputs,
            outputs: Outputs,
        ) -> None:
            if self.fail:
                self.fail = False
                raise ValueError("processing failed")
            super().process(context, configuration, inputs, outputs)

    prepared, procedure, _ = prepare(FailingOnceProcedure())
    inputs = Inputs._from_bindings({})
    outputs = Outputs._from_bindings({})

    with pytest.raises(ValueError, match="processing failed"):
        prepared.execute(inputs=inputs, outputs=outputs)

    prepared.execute(inputs=inputs, outputs=outputs)
    prepared.close()

    assert procedure.total == 4
    assert procedure.close_calls == 1


def test_setup_failure_does_not_call_close() -> None:
    class SetupFailure(CounterProcedure):
        def setup(
            self,
            context: ProcedureSetupContext,
            configuration: Config,
            inputs: SetupInputs,
        ) -> None:
            raise ValueError("setup failed")

    procedure = SetupFailure()

    with pytest.raises(ValueError, match="setup failed"):
        PreparedProcedure(
            procedure,
            Config(increment=2),
            SetupInputs._from_bindings({}),
        )

    assert procedure.close_calls == 0


def test_active_execution_rejects_reentry_and_close() -> None:
    started = Event()
    release = Event()

    class BlockingProcedure(CounterProcedure):
        def process(
            self,
            context: ProcedureProcessContext,
            configuration: Config,
            inputs: Inputs,
            outputs: Outputs,
        ) -> None:
            started.set()
            assert release.wait(timeout=1)

    prepared, _, _ = prepare(BlockingProcedure())
    inputs = Inputs._from_bindings({})
    outputs = Outputs._from_bindings({})

    with ThreadPoolExecutor(max_workers=1) as executor:
        execution = executor.submit(
            prepared.execute,
            inputs=inputs,
            outputs=outputs,
        )
        assert started.wait(timeout=1)

        with pytest.raises(RuntimeError, match="already executing"):
            prepared.execute(inputs=inputs, outputs=outputs)
        with pytest.raises(RuntimeError, match="cannot close an executing"):
            prepared.close()

        release.set()
        assert execution.result(timeout=1) is None


def test_unconfigured_procedure_receives_none_for_every_lifecycle_hook() -> None:
    configurations: list[None] = []

    class UnconfiguredProcedure(Procedure[None, SetupInputs, Inputs, Outputs]):
        def setup(
            self,
            context: ProcedureSetupContext,
            configuration: None,
            inputs: SetupInputs,
        ) -> None:
            configurations.append(configuration)

        def process(
            self,
            context: ProcedureProcessContext,
            configuration: None,
            inputs: Inputs,
            outputs: Outputs,
        ) -> None:
            configurations.append(configuration)

    prepared = PreparedProcedure(
        UnconfiguredProcedure(),
        None,
        SetupInputs._from_bindings({}),
    )

    prepared.execute(
        inputs=Inputs._from_bindings({}),
        outputs=Outputs._from_bindings({}),
    )

    assert configurations == [None, None]
