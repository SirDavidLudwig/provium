"""Tests for procedure preparation."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from provium import (
    Artifact,
    ArtifactDefinition,
    ArtifactHeader,
    ArtifactLineage,
    ArtifactReader,
    ArtifactRecord,
    ArtifactReference,
    ArtifactWriter,
    PreparedProcedure,
    Procedure,
    ProcedureConfig,
    ProcedureContract,
    ProcedureDefinition,
    ProcedureExecutionRecord,
    ProcedureExecutionResult,
    ProcedureExecutor,
    ProcedureProcessContext,
    ProcedureRecord,
    ProcedureSetupContext,
    decode_header,
    encode_header,
    input,
    optional_input,
    output,
    repeated_input,
)


class Config(ProcedureConfig):
    value: int = 1


class Contract(ProcedureContract[Config]):
    configuration = Config


class BytesReader(ArtifactReader):
    def read(self) -> bytes:
        return self.body.read()


class BytesWriter(ArtifactWriter):
    def write(self, value: bytes) -> int:
        return self.body.write(value)


BYTES = ArtifactDefinition(
    "example.ExecutorBytesV1",
    f"{__name__}:BytesArtifact",
    "Executor bytes.",
)


class BytesArtifact(Artifact[BytesReader, BytesWriter]):
    definition = BYTES
    reader = BytesReader
    writer = BytesWriter


def write_artifact(path: Path, identity: str, body: bytes) -> ArtifactRecord:
    reference = ArtifactReference(identity, BYTES.identifier)
    digest = hashlib.sha256(body).hexdigest()
    execution = ProcedureExecutionRecord(
        f"{identity}-execution",
        ProcedureRecord("example.SourceV1", "source-contract"),
        outputs=(reference,),
    )
    record = ArtifactRecord(reference, digest, execution.identity)
    lineage = ArtifactLineage.for_execution(execution, (record,))
    header = ArtifactHeader.create(
        artifact_identifier=reference.artifact_identifier,
        artifact_identity=reference.identity,
        body_length=len(body),
        body_digest=digest,
        lineage=lineage,
    )
    path.write_bytes(encode_header(header) + body)
    return record


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

    with pytest.raises(
        TypeError,
        match=(
            "invalid setup inputs for procedure example.ExecutorV1: "
            "unknown field: unexpected"
        ),
    ):
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

    result = ProcedureExecutor().execute(
        DEFINITION,
        configuration_layers=({"value": 4},),
        inputs={},
        outputs={},
    )

    assert isinstance(result, ProcedureExecutionResult)
    assert result.procedure.name == DEFINITION.identifier
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

    with pytest.raises(
        TypeError,
        match=(
            "invalid processing inputs for procedure example.ExecutorV1: "
            "unknown field: unexpected"
        ),
    ):
        ProcedureExecutor().execute(
            DEFINITION,
            inputs={"unexpected": object()},
            outputs={},
        )

    assert len(ExecutorProcedure.instances) == 1
    procedure = ExecutorProcedure.instances[0]
    assert procedure.process_inputs is None
    assert procedure.close_calls == 1


def test_execute_contextualizes_invalid_output_bindings_and_closes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ProcedureDefinition,
        "resolve",
        lambda self: ExecutorProcedure,
    )

    with pytest.raises(
        TypeError,
        match=(
            "invalid outputs for procedure example.ExecutorV1: "
            "unknown field: unexpected"
        ),
    ):
        ProcedureExecutor().execute(
            DEFINITION,
            inputs={},
            outputs={"unexpected": object()},  # type: ignore[dict-item]
        )

    assert len(ExecutorProcedure.instances) == 1
    assert ExecutorProcedure.instances[0].close_calls == 1


def test_execute_rejects_duplicate_output_destinations_before_processing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class OutputContract(ProcedureContract[None]):
        class Outputs(Contract.Outputs):
            first = output(BYTES)
            second = output(BYTES)

    definition = ProcedureDefinition(
        "example.DuplicateOutputsV1",
        f"{__name__}:OutputProcedure",
        "Duplicate outputs",
        None,
        OutputContract,
    )
    processed: list[bool] = []
    closed: list[bool] = []

    class OutputProcedure(
        Procedure[
            None,
            OutputContract.SetupInputs,
            OutputContract.Inputs,
            OutputContract.Outputs,
        ]
    ):
        def process(
            self,
            context: ProcedureProcessContext,
            configuration: None,
            inputs: OutputContract.Inputs,
            outputs: OutputContract.Outputs,
        ) -> None:
            processed.append(True)

        def close(self) -> None:
            closed.append(True)

    OutputProcedure.definition = definition

    monkeypatch.setattr(
        ProcedureDefinition,
        "resolve",
        lambda self: OutputProcedure,
    )
    destination = tmp_path / "same.pa"

    with pytest.raises(
        ValueError,
        match=(
            "invalid outputs for procedure example.DuplicateOutputsV1: "
            "fields first and second use the same destination"
        ),
    ):
        ProcedureExecutor().execute(
            definition,
            inputs={},
            outputs={
                "first": BytesArtifact.bind_write(destination),
                "second": BytesArtifact.bind_write(
                    destination.parent / "." / "same.pa"
                ),
            },
        )

    assert processed == []
    assert closed == [True]


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


def test_executor_runs_complete_typed_artifact_invocation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class FullConfig(ProcedureConfig):
        prefix: str = "default"

    class FullContract(ProcedureContract[FullConfig]):
        configuration = FullConfig

        class SetupInputs(Contract.SetupInputs):
            model = input(BYTES)

        class Inputs(Contract.Inputs):
            primary = input(BYTES)
            optional = optional_input(BYTES)
            extras = repeated_input(BYTES, minimum=2, maximum=2)

        class Outputs(Contract.Outputs):
            first = output(BYTES)
            second = output(BYTES)

    definition = ProcedureDefinition(
        "example.FullExecutorV1",
        f"{__name__}:FullProcedure",
        "Full executor",
        None,
        FullContract,
    )
    instances: list[FullProcedure] = []

    class FullProcedure(
        Procedure[
            FullConfig,
            FullContract.SetupInputs,
            FullContract.Inputs,
            FullContract.Outputs,
        ]
    ):
        def __init__(self) -> None:
            self.model = b""
            self.closed = False
            instances.append(self)

        def setup(
            self,
            context: ProcedureSetupContext,
            configuration: FullConfig,
            inputs: FullContract.SetupInputs,
        ) -> None:
            with inputs.model.open() as reader:
                self.model = reader.read()

        def process(
            self,
            context: ProcedureProcessContext,
            configuration: FullConfig,
            inputs: FullContract.Inputs,
            outputs: FullContract.Outputs,
        ) -> None:
            with inputs.primary.open() as reader:
                primary = reader.read()
            extras = []
            for binding in inputs.extras:
                with binding.open() as reader:
                    extras.append(reader.read())
            assert inputs.optional is None
            body = b"|".join(
                [configuration.prefix.encode(), self.model, primary, *extras]
            )
            outputs.first.open().write(body)
            outputs.second.open().write(body.upper())

        def close(self) -> None:
            self.closed = True

    FullProcedure.definition = definition
    monkeypatch.setattr(
        ProcedureDefinition,
        "resolve",
        lambda self: FullProcedure,
    )
    source_specs = (
        ("model", b"model"),
        ("primary", b"primary"),
        ("extra-1", b"extra one"),
        ("extra-2", b"extra two"),
    )
    records: dict[str, ArtifactRecord] = {}
    paths: dict[str, Path] = {}
    for identity, body in source_specs:
        path = tmp_path / f"{identity}.pa"
        paths[identity] = path
        records[identity] = write_artifact(path, identity, body)
    first_path = tmp_path / "first.pa"
    second_path = tmp_path / "second.pa"

    result = ProcedureExecutor().execute(
        definition,
        configuration_layers=({"prefix": "earlier"}, {"prefix": "final"}),
        setup_inputs={"model": BytesArtifact.bind_read(paths["model"])},
        inputs={
            "primary": BytesArtifact.bind_read(paths["primary"]),
            "extras": [
                BytesArtifact.bind_read(paths["extra-2"]),
                BytesArtifact.bind_read(paths["extra-1"]),
            ],
        },
        outputs={
            "first": BytesArtifact.bind_write(first_path),
            "second": BytesArtifact.bind_write(second_path),
        },
    )

    assert instances[0].closed
    assert result.procedure is not None
    assert result.procedure.config == {"prefix": "final"}
    assert result.inputs == tuple(
        records[name].reference for name in ("model", "primary", "extra-2", "extra-1")
    )
    assert tuple(result.outputs) == ("first", "second")
    expected_bodies = {
        first_path: b"final|model|primary|extra two|extra one",
        second_path: b"FINAL|MODEL|PRIMARY|EXTRA TWO|EXTRA ONE",
    }
    for path, expected_body in expected_bodies.items():
        data = path.read_bytes()
        header = decode_header(data)
        assert data[header.body_offset :] == expected_body
        assert header.lineage == result.lineage
