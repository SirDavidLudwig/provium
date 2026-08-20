from types import SimpleNamespace

import pytest

from provium import (
    Procedure,
    ProcedureContract,
    ProcedureDefinition,
    ProcedureInputs,
    ProcedureOutputs,
)


class Config:
    pass


class SetupInputs(ProcedureInputs):
    pass


class Inputs(ProcedureInputs):
    pass


class Outputs(ProcedureOutputs):
    pass


class Contract(ProcedureContract[Config]):
    configuration = Config
    SetupInputs = SetupInputs
    Inputs = Inputs
    Outputs = Outputs


EXAMPLE_DEFINITION = ProcedureDefinition(
    identifier="example.ExampleV1",
    target="example.procedures:ExampleProcedure",
    label="Example",
    description="An example procedure.",
    contract=Contract,
)


class ExampleProcedure(Procedure[Config, SetupInputs, Inputs, Outputs]):
    definition = EXAMPLE_DEFINITION


def test_procedure_is_a_specialized_class_with_a_definition() -> None:
    assert issubclass(ExampleProcedure, Procedure)
    assert ExampleProcedure.definition is EXAMPLE_DEFINITION


def test_procedure_definition_exposes_lightweight_metadata() -> None:
    assert EXAMPLE_DEFINITION.identifier == "example.ExampleV1"
    assert EXAMPLE_DEFINITION.target == "example.procedures:ExampleProcedure"
    assert EXAMPLE_DEFINITION.label == "Example"
    assert EXAMPLE_DEFINITION.description == "An example procedure."
    assert EXAMPLE_DEFINITION.contract is Contract


def test_procedure_definition_description_is_optional() -> None:
    definition = ProcedureDefinition(
        "example.ExampleV1",
        "example.procedures:ExampleProcedure",
        "Example",
        None,
        Contract,
    )

    assert definition.description is None


@pytest.mark.parametrize("field", ["identifier", "target", "label"])
def test_procedure_definition_requires_nonempty_text(field: str) -> None:
    values: dict[str, object] = {
        "identifier": "example.ExampleV1",
        "target": "example.procedures:ExampleProcedure",
        "label": "Example",
        "description": None,
        "contract": Contract,
    }
    values[field] = ""

    with pytest.raises(ValueError, match=field):
        ProcedureDefinition(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize("field", ["identifier", "target", "label", "description"])
def test_procedure_definition_requires_text_values(field: str) -> None:
    values: dict[str, object] = {
        "identifier": "example.ExampleV1",
        "target": "example.procedures:ExampleProcedure",
        "label": "Example",
        "description": "An example procedure.",
        "contract": Contract,
    }
    values[field] = object()

    with pytest.raises(TypeError, match=field):
        ProcedureDefinition(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize("contract", [object, Contract()])
def test_procedure_definition_requires_a_contract_class(contract: object) -> None:
    with pytest.raises(TypeError, match="ProcedureContract"):
        ProcedureDefinition(
            "example.ExampleV1",
            "example.procedures:ExampleProcedure",
            "Example",
            None,
            contract,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "target",
    [
        "example.procedures",
        ":ExampleProcedure",
        "example.procedures:",
        "example..procedures:ExampleProcedure",
        "example.procedures:.ExampleProcedure",
        "example.procedures:ExampleProcedure.",
        "example procedures:ExampleProcedure",
        "example.procedures:Example Procedure",
        "example.procedures:Example:Procedure",
    ],
)
def test_procedure_definition_requires_module_attribute_target(target: str) -> None:
    with pytest.raises(ValueError, match="module:attribute"):
        ProcedureDefinition(
            "example.ExampleV1",
            target,
            "Example",
            None,
            Contract,
        )


def test_procedure_definition_resolves_lazily_and_checks_resolution_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    imports: list[str] = []

    def import_module(name: str) -> object:
        imports.append(name)
        return SimpleNamespace(nested=SimpleNamespace(Example=ExampleProcedure))

    monkeypatch.setattr("provium.procedure.definition.import_module", import_module)
    definition = ProcedureDefinition(
        "example.ExampleV1",
        "example.procedures:nested.Example",
        "Example",
        None,
        Contract,
    )
    monkeypatch.setattr(
        ExampleProcedure,
        "definition",
        ProcedureDefinition(
            "example.ExampleV1",
            "example.procedures:nested.Example",
            "Different label",
            "Different description.",
            Contract,
        ),
    )

    assert imports == []
    assert definition.resolve() is ExampleProcedure
    assert imports == ["example.procedures"]


def test_procedure_definition_rejects_mismatched_resolution_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    definition = ProcedureDefinition(
        "example.ExampleV1",
        "example.procedures:ExampleProcedure",
        "Example",
        None,
        Contract,
    )
    target = SimpleNamespace(
        definition=SimpleNamespace(
            identifier="example.OtherV1",
            target="example.procedures:ExampleProcedure",
        )
    )
    monkeypatch.setattr(
        "provium.procedure.definition.import_module",
        lambda name: SimpleNamespace(value=target),
    )
    definition = ProcedureDefinition(
        "example.ExampleV1",
        "example.procedures:value",
        "Example",
        None,
        Contract,
    )

    with pytest.raises(ValueError, match="identifier and target"):
        definition.resolve()
