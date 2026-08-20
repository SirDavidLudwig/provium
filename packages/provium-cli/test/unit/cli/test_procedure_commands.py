from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pytest

from provium import (
    Artifact,
    ArtifactDefinition,
    ArtifactReader,
    ArtifactWriter,
    Procedure,
    ProcedureCatalog,
    ProcedureConfig,
    ProcedureContract,
    ProcedureDefinition,
    ProcedureExecutionResult,
    ProcedureInputs,
    ProcedureOutputs,
    ProcedureProcessContext,
    input,
    optional_input,
    output,
    repeated_input,
)
from provium_cli import run
from provium_cli.commands.procedure import ExecuteCommand, ProcedureCommand


class Reader(ArtifactReader):
    pass


class Writer(ArtifactWriter):
    pass


ARTIFACT = ArtifactDefinition(
    "example.DataV1", f"{__name__}:DataArtifact", "Example data"
)


class DataArtifact(Artifact[Reader, Writer]):
    definition = ARTIFACT
    reader = Reader
    writer = Writer


class Config(ProcedureConfig):
    value: int = 1


class Contract(ProcedureContract[Config]):
    configuration = Config

    class SetupInputs(ProcedureInputs):
        model = input(ARTIFACT)

    class Inputs(ProcedureInputs):
        source = input(ARTIFACT)
        previous = optional_input(ARTIFACT)
        extras = repeated_input(ARTIFACT, minimum=1)

    class Outputs(ProcedureOutputs):
        result = output(ARTIFACT)


class EmptyContract(ProcedureContract[None]):
    configuration = None


DEFINITION = ProcedureDefinition(
    "example.ProcessV1",
    f"{__name__}:Implementation",
    "Process data",
    "Process example data.",
    Contract,
)


class Implementation(
    Procedure[Config, Contract.SetupInputs, Contract.Inputs, Contract.Outputs]
):
    definition = DEFINITION

    def process(
        self,
        context: ProcedureProcessContext,
        configuration: Config,
        inputs: Contract.Inputs,
        outputs: Contract.Outputs,
    ) -> None:
        pass


@pytest.fixture
def catalog(monkeypatch: pytest.MonkeyPatch) -> ProcedureCatalog:
    result = ProcedureCatalog()
    result.register(DEFINITION)
    monkeypatch.setattr(
        "provium_cli.commands.procedure.discover_procedure_catalogs",
        lambda: result,
    )
    return result


def test_procedure_list_is_sorted_and_does_not_resolve(
    catalog: ProcedureCatalog,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        ProcedureDefinition,
        "resolve",
        lambda self: pytest.fail("quick listing must not resolve"),
    )

    assert run(["procedure", "list"]) == 0
    assert capsys.readouterr().out == "example.ProcessV1\tProcess data\n"


def test_procedure_show_renders_lazy_contract_metadata(
    catalog: ProcedureCatalog,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        ProcedureDefinition,
        "resolve",
        lambda self: pytest.fail("quick show must not resolve"),
    )

    assert run(["procedure", "show", DEFINITION.identifier]) == 0
    output_text = capsys.readouterr().out
    assert "Process data" in output_text
    assert "Process example data." in output_text
    assert DEFINITION.invocation_synopsis in output_text
    assert "example.DataV1" in output_text
    assert '"value"' in output_text


def test_procedure_show_can_explicitly_resolve(
    catalog: ProcedureCatalog,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(ProcedureDefinition, "resolve", lambda self: Implementation)

    assert run(["procedure", "show", DEFINITION.identifier, "--resolve"]) == 0
    assert f"Resolved: {__name__}.Implementation" in capsys.readouterr().out


def test_unknown_procedure_reports_a_cli_error(
    catalog: ProcedureCatalog,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert run(["procedure", "show", "missing"]) == 2
    assert "unknown procedure: missing" in capsys.readouterr().err


def test_show_handles_empty_contract_without_description(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    definition = ProcedureDefinition(
        "example.EmptyV1",
        f"{__name__}:Implementation",
        "Empty",
        None,
        EmptyContract,
    )
    discovered = ProcedureCatalog()
    discovered.register(definition)
    monkeypatch.setattr(
        "provium_cli.commands.procedure.discover_procedure_catalogs",
        lambda: discovered,
    )

    assert run(["procedure", "show", definition.identifier]) == 0
    assert "Configuration:" not in capsys.readouterr().out


def test_execute_builds_layered_typed_bindings(
    catalog: ProcedureCatalog,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configuration = tmp_path / "config.json"
    configuration.write_text(json.dumps({"value": 4}))
    received: dict[str, Any] = {}

    def execute(self: object, definition: object, **arguments: object) -> object:
        received.update(arguments)
        return ProcedureExecutionResult("execution", None, ())

    monkeypatch.setattr(
        "provium_cli.commands.procedure.ProcedureExecutor.execute", execute
    )

    assert (
        run(
            [
                "execute",
                DEFINITION.identifier,
                "--config",
                str(configuration),
                "--setup-input",
                "model=model.pa",
                "--input",
                "source=source.pa",
                "--input",
                "extras=first.pa",
                "--input",
                "extras=second.pa",
                "--output",
                "result=result.pa",
            ]
        )
        == 0
    )
    assert received["configuration_layers"] == ({"value": 4},)
    assert received["setup_inputs"]["model"].path == Path("model.pa")
    assert received["inputs"]["source"].path == Path("source.pa")
    assert [binding.path for binding in received["inputs"]["extras"]] == [
        Path("first.pa"),
        Path("second.pa"),
    ]
    assert received["outputs"]["result"].path == Path("result.pa")
    assert capsys.readouterr().out == "execution\n"


def test_execute_reports_invalid_binding_syntax(
    catalog: ProcedureCatalog,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert run(["execute", DEFINITION.identifier, "--input", "invalid"]) == 2
    assert "FIELD=PATH" in capsys.readouterr().err


def test_execute_reports_runtime_failures_as_cli_errors(
    catalog: ProcedureCatalog,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise RuntimeError("processing failed")

    monkeypatch.setattr(
        "provium_cli.commands.procedure.ProcedureExecutor.execute", fail
    )

    assert run(["execute", DEFINITION.identifier]) == 2
    assert "processing failed" in capsys.readouterr().err


def test_configuration_loader_supports_yaml_and_rejects_unknown_suffix(
    tmp_path: Path,
) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("value: 3\n")

    assert ExecuteCommand._load_configuration(str(path)) == {"value": 3}
    with pytest.raises(ValueError, match="unsupported configuration"):
        ExecuteCommand._load_configuration(str(tmp_path / "config.txt"))


def test_binding_helpers_reject_unknown_and_duplicate_fields() -> None:
    with pytest.raises(ValueError, match="unknown binding field"):
        ExecuteCommand._read_bindings(Contract.Inputs.fields, ["missing=value.pa"])
    with pytest.raises(ValueError, match="may be supplied only once"):
        ExecuteCommand._read_bindings(
            Contract.Inputs.fields,
            ["source=first.pa", "source=second.pa"],
        )


@pytest.mark.parametrize("command", [ProcedureCommand(), ExecuteCommand()])
def test_commands_reject_direct_execution_without_configured_action(
    command: ProcedureCommand | ExecuteCommand,
) -> None:
    with pytest.raises(AttributeError):
        command.execute(argparse.Namespace())
