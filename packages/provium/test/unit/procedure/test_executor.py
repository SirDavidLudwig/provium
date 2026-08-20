"""Tests for procedure preparation."""

from __future__ import annotations

import pytest

from provium import (
    PreparedProcedure,
    Procedure,
    ProcedureConfig,
    ProcedureContract,
    ProcedureDefinition,
    ProcedureExecutor,
    ProcedureProcessContext,
    ProcedureSetupContext,
)


class Config(ProcedureConfig):
    value: int = 1


class Contract(ProcedureContract[Config]):
    configuration = Config


DEFINITION = ProcedureDefinition(
    "example.ExecutorV1",
    "example.procedures:ExecutorProcedure",
    "Executor",
    None,
    Contract,
)


class ExecutorProcedure(
    Procedure[
        Config,
        Contract.SetupInputs,
        Contract.Inputs,
        Contract.Outputs,
    ]
):
    definition = DEFINITION
    instances: list[ExecutorProcedure] = []

    def __init__(self) -> None:
        self.setup_configuration: Config | None = None
        self.setup_inputs: Contract.SetupInputs | None = None
        self.process_configuration: Config | None = None
        self.process_inputs: Contract.Inputs | None = None
        self.process_outputs: Contract.Outputs | None = None
        self.close_calls = 0
        type(self).instances.append(self)

    def setup(
        self,
        context: ProcedureSetupContext,
        configuration: Config,
        inputs: Contract.SetupInputs,
    ) -> None:
        self.setup_configuration = configuration
        self.setup_inputs = inputs

    def process(
        self,
        context: ProcedureProcessContext,
        configuration: Config,
        inputs: Contract.Inputs,
        outputs: Contract.Outputs,
    ) -> None:
        self.process_configuration = configuration
        self.process_inputs = inputs
        self.process_outputs = outputs

    def close(self) -> None:
        self.close_calls += 1


@pytest.fixture(autouse=True)
def reset_instances() -> None:
    ExecutorProcedure.instances.clear()


def test_prepare_resolves_configures_and_sets_up_a_fresh_procedure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolutions: list[ProcedureDefinition[ExecutorProcedure]] = []

    def resolve(
        definition: ProcedureDefinition[ExecutorProcedure],
    ) -> type[ExecutorProcedure]:
        resolutions.append(definition)
        return ExecutorProcedure

    monkeypatch.setattr(ProcedureDefinition, "resolve", resolve)

    prepared = ProcedureExecutor().prepare(
        DEFINITION,
        configuration_layers=({"value": 2}, {"value": 3}),
    )

    assert isinstance(prepared, PreparedProcedure)
    assert prepared.configuration == Config(value=3)
    assert resolutions == [DEFINITION]
    assert len(ExecutorProcedure.instances) == 1
    procedure = ExecutorProcedure.instances[0]
    assert procedure.setup_configuration is prepared.configuration
    assert isinstance(procedure.setup_inputs, Contract.SetupInputs)


def test_prepare_validates_configuration_before_instantiation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ProcedureDefinition,
        "resolve",
        lambda self: ExecutorProcedure,
    )

    with pytest.raises(ValueError, match="invalid configuration for procedure"):
        ProcedureExecutor().prepare(
            DEFINITION,
            configuration_layers=({"value": "invalid"},),
        )

    assert ExecutorProcedure.instances == []


def test_prepare_validates_setup_bindings_before_instantiation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ProcedureDefinition,
        "resolve",
        lambda self: ExecutorProcedure,
    )

    with pytest.raises(TypeError, match="unknown field: unexpected"):
        ProcedureExecutor().prepare(
            DEFINITION,
            setup_inputs={"unexpected": object()},
        )

    assert ExecutorProcedure.instances == []


def test_prepare_supplies_none_to_an_unconfigured_procedure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class UnconfiguredContract(ProcedureContract[None]):
        configuration = None

    definition = ProcedureDefinition(
        "example.UnconfiguredV1",
        "example.procedures:UnconfiguredProcedure",
        "Unconfigured",
        None,
        UnconfiguredContract,
    )
    configurations: list[None] = []

    class UnconfiguredProcedure(
        Procedure[
            None,
            UnconfiguredContract.SetupInputs,
            UnconfiguredContract.Inputs,
            UnconfiguredContract.Outputs,
        ]
    ):
        def setup(
            self,
            context: ProcedureSetupContext,
            configuration: None,
            inputs: UnconfiguredContract.SetupInputs,
        ) -> None:
            configurations.append(configuration)

        def process(
            self,
            context: ProcedureProcessContext,
            configuration: None,
            inputs: UnconfiguredContract.Inputs,
            outputs: UnconfiguredContract.Outputs,
        ) -> None:
            pass

    UnconfiguredProcedure.definition = definition

    monkeypatch.setattr(
        ProcedureDefinition,
        "resolve",
        lambda self: UnconfiguredProcedure,
    )

    prepared = ProcedureExecutor().prepare(definition)

    assert prepared.configuration is None
    assert configurations == [None]


def test_unconfigured_procedure_rejects_configuration_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class UnconfiguredContract(ProcedureContract[None]):
        configuration = None

    definition = ProcedureDefinition(
        "example.UnconfiguredV1",
        "example.procedures:UnconfiguredProcedure",
        "Unconfigured",
        None,
        UnconfiguredContract,
    )
    monkeypatch.setattr(
        ProcedureDefinition,
        "resolve",
        lambda self: ExecutorProcedure,
    )

    with pytest.raises(TypeError, match="does not accept configuration"):
        ProcedureExecutor().prepare(
            definition,
            configuration_layers=({"unexpected": True},),
        )

    assert ExecutorProcedure.instances == []


def test_prepare_rejects_a_procedure_requiring_constructor_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class RequiredArgumentProcedure(ExecutorProcedure):
        def __init__(self, required: object) -> None:
            super().__init__()

    monkeypatch.setattr(
        ProcedureDefinition,
        "resolve",
        lambda self: RequiredArgumentProcedure,
    )

    with pytest.raises(
        TypeError,
        match="procedure example.ExecutorV1 must be constructible without arguments",
    ):
        ProcedureExecutor().prepare(DEFINITION)

    assert ExecutorProcedure.instances == []


def test_prepare_preserves_an_error_raised_inside_the_constructor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ConstructorFailure(ExecutorProcedure):
        def __init__(self) -> None:
            raise TypeError("constructor implementation failed")

    monkeypatch.setattr(
        ProcedureDefinition,
        "resolve",
        lambda self: ConstructorFailure,
    )

    with pytest.raises(TypeError, match="constructor implementation failed"):
        ProcedureExecutor().prepare(DEFINITION)


def test_execute_runs_one_typed_invocation_and_closes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ProcedureDefinition,
        "resolve",
        lambda self: ExecutorProcedure,
    )

    assert (
        ProcedureExecutor().execute(
            DEFINITION,
            configuration_layers=({"value": 4},),
            inputs={},
            outputs={},
        )
        is None
    )

    assert len(ExecutorProcedure.instances) == 1
    procedure = ExecutorProcedure.instances[0]
    assert isinstance(procedure.process_inputs, Contract.Inputs)
    assert isinstance(procedure.process_outputs, Contract.Outputs)
    assert procedure.process_configuration is procedure.setup_configuration
    assert procedure.close_calls == 1


def test_execute_closes_when_processing_bindings_are_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ProcedureDefinition,
        "resolve",
        lambda self: ExecutorProcedure,
    )

    with pytest.raises(TypeError, match="unknown field: unexpected"):
        ProcedureExecutor().execute(
            DEFINITION,
            inputs={"unexpected": object()},
            outputs={},
        )

    assert len(ExecutorProcedure.instances) == 1
    procedure = ExecutorProcedure.instances[0]
    assert procedure.process_inputs is None
    assert procedure.close_calls == 1


def test_execute_preserves_processing_error_when_close_also_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    close_error = RuntimeError("close failed")

    class FailingProcedure(ExecutorProcedure):
        def process(
            self,
            context: ProcedureProcessContext,
            configuration: Config,
            inputs: Contract.Inputs,
            outputs: Contract.Outputs,
        ) -> None:
            raise ValueError("processing failed")

        def close(self) -> None:
            raise close_error

    monkeypatch.setattr(
        ProcedureDefinition,
        "resolve",
        lambda self: FailingProcedure,
    )

    with pytest.raises(ValueError, match="processing failed") as caught:
        ProcedureExecutor().execute(DEFINITION, inputs={}, outputs={})

    assert caught.value.__cause__ is close_error
