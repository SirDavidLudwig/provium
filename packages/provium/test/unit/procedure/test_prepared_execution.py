"""Tests for prepared procedure output execution."""

from pathlib import Path

import pytest
from pydantic import Field

from provium import (
    Artifact,
    ArtifactDefinition,
    ArtifactReader,
    ArtifactWriter,
    PreparedProcedure,
    Procedure,
    ProcedureConfig,
    ProcedureContract,
    ProcedureDefinition,
    ProcedureInputs,
    ProcedureOutputs,
    ProcedureProcessContext,
    decode_header,
    output,
    session,
)


class BytesReader(ArtifactReader):
    pass


class BytesWriter(ArtifactWriter):
    def write(self, value: bytes) -> int:
        return self.body.write(value)


BYTES = ArtifactDefinition(
    "example.PreparedBytesV1",
    f"{__name__}:BytesArtifact",
    "Prepared procedure bytes.",
)


class BytesArtifact(Artifact[BytesReader, BytesWriter]):
    definition = BYTES
    reader = BytesReader
    writer = BytesWriter


class Contract(ProcedureContract[None]):
    class Inputs(ProcedureInputs):
        pass

    class Outputs(ProcedureOutputs):
        result = output(BYTES)


DEFINITION = ProcedureDefinition(
    "example.PreparedOutputV1",
    f"{__name__}:WritingProcedure",
    "Write output",
    None,
    Contract,
)


class WritingProcedure(
    Procedure[None, Contract.SetupInputs, Contract.Inputs, Contract.Outputs]
):
    definition = DEFINITION

    def process(
        self,
        context: ProcedureProcessContext,
        configuration: None,
        inputs: Contract.Inputs,
        outputs: Contract.Outputs,
    ) -> None:
        with outputs.result.open() as writer:
            writer.write(b"result")


def prepare(
    procedure: WritingProcedure | None = None,
) -> PreparedProcedure[None, Contract.Inputs, Contract.Outputs]:
    return PreparedProcedure(
        WritingProcedure() if procedure is None else procedure,
        None,
        Contract.SetupInputs._from_bindings({}),
    )


def test_prepared_execution_stages_and_publishes_declared_output(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "result.pa"
    binding = BytesArtifact.bind_write(destination)

    with session():
        prepared = prepare()
        assert (
            prepared.execute(
                inputs=Contract.Inputs._from_bindings({}),
                outputs=Contract.Outputs._from_bindings({"result": binding}),
            )
            is None
        )

    data = destination.read_bytes()
    header = decode_header(data)
    record = next(iter(header.lineage.artifacts.values()))
    execution = header.lineage.producing_execution(record.reference)
    assert execution.procedure.name == DEFINITION.identifier
    assert execution.procedure.version == Contract.metadata.digest
    assert execution.procedure.config is None
    assert execution.procedure.config_codec is None
    assert data[header.body_offset :] == b"result"


def test_callback_rejects_an_equal_but_undeclared_output_binding(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "result.pa"

    class UndeclaredBindingProcedure(WritingProcedure):
        def process(
            self,
            context: ProcedureProcessContext,
            configuration: None,
            inputs: Contract.Inputs,
            outputs: Contract.Outputs,
        ) -> None:
            BytesArtifact.bind_write(destination).open()

    with session(), pytest.raises(RuntimeError, match="not declared"):
        prepare(UndeclaredBindingProcedure()).execute(
            inputs=Contract.Inputs._from_bindings({}),
            outputs=Contract.Outputs._from_bindings(
                {"result": BytesArtifact.bind_write(destination)}
            ),
        )

    assert not destination.exists()


def test_processing_failure_preserves_existing_output(tmp_path: Path) -> None:
    destination = tmp_path / "result.pa"
    destination.write_bytes(b"existing")

    class FailingProcedure(WritingProcedure):
        def process(
            self,
            context: ProcedureProcessContext,
            configuration: None,
            inputs: Contract.Inputs,
            outputs: Contract.Outputs,
        ) -> None:
            outputs.result.open().write(b"replacement")
            raise ValueError("processing failed")

    with session(), pytest.raises(ValueError, match="processing failed"):
        prepare(FailingProcedure()).execute(
            inputs=Contract.Inputs._from_bindings({}),
            outputs=Contract.Outputs._from_bindings(
                {"result": BytesArtifact.bind_write(destination)}
            ),
        )

    assert destination.read_bytes() == b"existing"


def test_output_binding_cannot_open_outside_a_procedure_callback(
    tmp_path: Path,
) -> None:
    with pytest.raises(RuntimeError, match="active procedure callback"):
        BytesArtifact.bind_write(tmp_path / "result.pa").open()


def test_prepared_execution_records_canonical_configuration(tmp_path: Path) -> None:
    class Config(ProcedureConfig):
        internal_value: int = Field(alias="external-value")

    class ConfiguredContract(ProcedureContract[Config]):
        configuration = Config

        class Inputs(ProcedureInputs):
            pass

        class Outputs(ProcedureOutputs):
            result = output(BYTES)

    definition = ProcedureDefinition(
        "example.ConfiguredOutputV1",
        f"{__name__}:ConfiguredProcedure",
        "Write configured output",
        None,
        ConfiguredContract,
    )

    class ConfiguredProcedure(
        Procedure[
            Config,
            ConfiguredContract.SetupInputs,
            ConfiguredContract.Inputs,
            ConfiguredContract.Outputs,
        ]
    ):
        def process(
            self,
            context: ProcedureProcessContext,
            configuration: Config,
            inputs: ConfiguredContract.Inputs,
            outputs: ConfiguredContract.Outputs,
        ) -> None:
            outputs.result.open().write(str(configuration.internal_value).encode())

    ConfiguredProcedure.definition = definition
    destination = tmp_path / "configured.pa"
    prepared = PreparedProcedure(
        ConfiguredProcedure(),
        Config(**{"external-value": 7}),
        ConfiguredContract.SetupInputs._from_bindings({}),
    )

    with session():
        prepared.execute(
            inputs=ConfiguredContract.Inputs._from_bindings({}),
            outputs=ConfiguredContract.Outputs._from_bindings(
                {"result": BytesArtifact.bind_write(destination)}
            ),
        )

    header = decode_header(destination.read_bytes())
    execution = next(iter(header.lineage.executions.values()))
    assert execution.procedure.config == {"external-value": 7}
    assert execution.procedure.config_codec == "pydantic-v2"


def test_no_output_callback_still_rejects_undeclared_write_binding(
    tmp_path: Path,
) -> None:
    class EmptyOutputs(ProcedureOutputs):
        pass

    class UndeclaredOutputProcedure(
        Procedure[None, ProcedureInputs, ProcedureInputs, EmptyOutputs]
    ):
        def process(
            self,
            context: ProcedureProcessContext,
            configuration: None,
            inputs: ProcedureInputs,
            outputs: EmptyOutputs,
        ) -> None:
            BytesArtifact.bind_write(tmp_path / "undeclared.pa").open()

    prepared = PreparedProcedure(
        UndeclaredOutputProcedure(),
        None,
        ProcedureInputs._from_bindings({}),
    )

    with pytest.raises(RuntimeError, match="not declared"):
        prepared.execute(
            inputs=ProcedureInputs._from_bindings({}),
            outputs=EmptyOutputs._from_bindings({}),
        )
