import json
from types import SimpleNamespace

import pytest

from provium import (
    Artifact,
    ArtifactDefinition,
    ArtifactReader,
    ArtifactWriter,
    Procedure,
    ProcedureConfig,
    ProcedureContract,
    ProcedureContractMetadata,
    ProcedureDefinition,
    ProcedureInputs,
    ProcedureIOFieldMetadata,
    ProcedureOutputs,
    input,
    optional_output,
    repeated_input,
)


class Config(ProcedureConfig):
    pass


class OtherConfig(ProcedureConfig):
    pass


class RequiredConfig(ProcedureConfig):
    value: int


class Reader(ArtifactReader):
    pass


class Writer(ArtifactWriter):
    pass


class ExampleArtifact(Artifact[Reader, Writer]):
    definition = ArtifactDefinition(
        "example.ExampleArtifactV1",
        "example.artifacts:ExampleArtifact",
        "An example artifact.",
    )
    reader = Reader
    writer = Writer


EXAMPLE_ARTIFACT: ArtifactDefinition[ExampleArtifact] = ExampleArtifact.definition


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


@pytest.mark.parametrize(
    ("attribute", "value", "message"),
    [
        ("configuration", object, "ProcedureConfig class or None"),
        ("configuration", Config(), "ProcedureConfig class or None"),
        ("SetupInputs", Outputs, "ProcedureInputs class"),
        ("Inputs", Outputs, "ProcedureInputs class"),
        ("Outputs", Inputs, "ProcedureOutputs class"),
    ],
)
def test_procedure_contract_validates_runtime_declarations(
    attribute: str, value: object, message: str
) -> None:
    with pytest.raises(TypeError, match=message):
        type(
            "InvalidContract",
            (ProcedureContract,),
            {attribute: value},
        )


def test_procedure_contract_cannot_override_compilation_hooks() -> None:
    with pytest.raises(TypeError, match="cannot override contract compilation"):

        class InvalidContract(ProcedureContract[Config]):
            configuration = Config
            Outputs = Inputs  # type: ignore[assignment]

            @classmethod
            def _validate_io_declarations(cls) -> None:
                pass


def test_procedure_contract_configuration_matches_generic_specialization() -> None:
    with pytest.raises(TypeError, match="configuration does not match"):

        class InvalidContract(ProcedureContract[Config]):
            configuration = OtherConfig


def test_unconfigured_procedure_contract_uses_none_specialization() -> None:
    class NoConfigContract(ProcedureContract[None]):
        configuration = None

    assert NoConfigContract.configuration is None


def test_contract_compiles_immutable_configuration_metadata() -> None:
    assert isinstance(Contract.metadata, ProcedureContractMetadata)
    assert Contract.metadata.configuration_target == (
        f"{Config.__module__}:{Config.__qualname__}"
    )
    assert Contract.metadata.configuration_schema == Config.model_json_schema()
    assert len(Contract.metadata.configuration_schema_digest or "") == 64
    assert len(Contract.metadata.digest) == 64

    schema = Contract.metadata.configuration_schema
    assert schema is not None
    schema["title"] = "Changed"
    assert Contract.metadata.configuration_schema == Config.model_json_schema()


def test_compiled_configuration_schema_is_json_serializable() -> None:
    assert json.loads(json.dumps(Contract.metadata.configuration_schema)) == (
        Config.model_json_schema()
    )


def test_contract_freezes_nested_configuration_schema_collections() -> None:
    class RequiredContract(ProcedureContract[RequiredConfig]):
        configuration = RequiredConfig

    assert RequiredContract.metadata.configuration_schema is not None
    assert RequiredContract.metadata.configuration_schema["required"] == ["value"]


def test_unconfigured_contract_compiles_absent_configuration_metadata() -> None:
    class NoConfigContract(ProcedureContract[None]):
        configuration = None

    assert NoConfigContract.metadata.configuration_target is None
    assert NoConfigContract.metadata.configuration_schema is None
    assert NoConfigContract.metadata.configuration_schema_digest is None


def test_contract_compiles_ordered_io_field_metadata_without_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ArtifactDefinition,
        "resolve",
        lambda self: pytest.fail("contract metadata must not resolve artifacts"),
    )

    class MetadataContract(ProcedureContract[Config]):
        configuration = Config

        class SetupInputs(ProcedureInputs):
            model = input(EXAMPLE_ARTIFACT, description="The setup model.")

        class Inputs(ProcedureInputs):
            first = input(EXAMPLE_ARTIFACT)
            values = repeated_input(EXAMPLE_ARTIFACT, minimum=1, maximum=4)

        class Outputs(ProcedureOutputs):
            preview = optional_output(EXAMPLE_ARTIFACT)

    assert MetadataContract.metadata.setup_inputs == (
        ProcedureIOFieldMetadata(
            name="model",
            artifact_identifier="example.ExampleArtifactV1",
            artifact_description="An example artifact.",
            direction="input",
            minimum=1,
            maximum=1,
            repeated=False,
            description="The setup model.",
        ),
    )
    assert [field.name for field in MetadataContract.metadata.inputs] == [
        "first",
        "values",
    ]
    assert MetadataContract.metadata.inputs[1].minimum == 1
    assert MetadataContract.metadata.inputs[1].maximum == 4
    assert MetadataContract.metadata.inputs[1].repeated is True
    assert MetadataContract.metadata.outputs[0].required is False


def test_equivalent_contract_inheritance_preserves_the_digest() -> None:
    class EquivalentContract(Contract):
        pass

    assert EquivalentContract.metadata == Contract.metadata


def test_contract_digest_changes_with_field_metadata() -> None:
    class FirstContract(ProcedureContract[Config]):
        configuration = Config

        class Inputs(ProcedureInputs):
            value = input(EXAMPLE_ARTIFACT, description="First description.")

    class SecondContract(ProcedureContract[Config]):
        configuration = Config

        class Inputs(ProcedureInputs):
            value = input(EXAMPLE_ARTIFACT, description="Second description.")

    assert FirstContract.metadata.digest != SecondContract.metadata.digest


def test_procedure_contract_requires_a_concrete_generic_specialization() -> None:
    with pytest.raises(TypeError, match="exactly one generic specialization"):

        class UnspecializedContract[ConfigT: ProcedureConfig](
            ProcedureContract[ConfigT]
        ):
            configuration = Config


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
