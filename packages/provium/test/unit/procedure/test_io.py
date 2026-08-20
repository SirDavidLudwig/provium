"""Tests for declarative procedure I/O fields."""

import pytest

from provium import (
    Artifact,
    ArtifactDefinition,
    ArtifactReader,
    ArtifactWriter,
    ProcedureInputs,
    ProcedureOutputs,
    input,
    output,
)


class Reader(ArtifactReader):
    pass


class Writer(ArtifactWriter):
    pass


class ExampleArtifact(Artifact[Reader, Writer]):
    definition = ArtifactDefinition(
        "example.ExampleV1",
        "example.artifacts:ExampleArtifact",
        "An example artifact.",
    )
    reader = Reader
    writer = Writer


EXAMPLE_ARTIFACT: ArtifactDefinition[ExampleArtifact] = ExampleArtifact.definition
OTHER_ARTIFACT: ArtifactDefinition[ExampleArtifact] = ArtifactDefinition(
    "example.OtherV1",
    "example.artifacts:OtherArtifact",
    "Another artifact.",
)


def test_required_input_exposes_ordered_metadata() -> None:
    class Inputs(ProcedureInputs):
        first = input(EXAMPLE_ARTIFACT, description="The first input.")
        second = input(EXAMPLE_ARTIFACT)

    assert list(Inputs.fields) == ["first", "second"]
    assert Inputs.fields["first"] is Inputs.first
    assert Inputs.first.name == "first"
    assert Inputs.first.artifact is EXAMPLE_ARTIFACT
    assert Inputs.first.direction == "input"
    assert Inputs.first.minimum == 1
    assert Inputs.first.maximum == 1
    assert Inputs.first.required is True
    assert Inputs.first.description == "The first input."


def test_required_output_exposes_ordered_metadata() -> None:
    class Outputs(ProcedureOutputs):
        result = output(EXAMPLE_ARTIFACT, description="The result.")

    assert list(Outputs.fields) == ["result"]
    assert Outputs.fields["result"] is Outputs.result
    assert Outputs.result.name == "result"
    assert Outputs.result.artifact is EXAMPLE_ARTIFACT
    assert Outputs.result.direction == "output"
    assert Outputs.result.minimum == 1
    assert Outputs.result.maximum == 1
    assert Outputs.result.required is True
    assert Outputs.result.description == "The result."


def test_io_fields_are_inherited_before_new_fields() -> None:
    class BaseInputs(ProcedureInputs):
        inherited = input(EXAMPLE_ARTIFACT)

    class Inputs(BaseInputs):
        local = input(EXAMPLE_ARTIFACT)

    assert list(Inputs.fields) == ["inherited", "local"]


def test_io_field_metadata_mapping_is_read_only() -> None:
    class Inputs(ProcedureInputs):
        value = input(EXAMPLE_ARTIFACT)

    try:
        Inputs.fields["other"] = Inputs.value  # type: ignore[index]
    except TypeError:
        pass
    else:
        raise AssertionError("procedure I/O field metadata must be read-only")


def test_inputs_reject_output_fields() -> None:
    with pytest.raises(TypeError, match="Inputs.value must be an input field"):

        class Inputs(ProcedureInputs):
            value = output(EXAMPLE_ARTIFACT)


def test_outputs_reject_input_fields() -> None:
    with pytest.raises(TypeError, match="Outputs.value must be an output field"):

        class Outputs(ProcedureOutputs):
            value = input(EXAMPLE_ARTIFACT)


def test_description_must_be_a_string() -> None:
    with pytest.raises(TypeError, match="description must be a string"):
        input(EXAMPLE_ARTIFACT, description=1)  # type: ignore[arg-type]


def test_description_must_be_nonempty_when_provided() -> None:
    with pytest.raises(ValueError, match="description must be nonempty"):
        input(EXAMPLE_ARTIFACT, description=" \t")


def test_unassigned_field_has_no_name() -> None:
    field = input(EXAMPLE_ARTIFACT)

    with pytest.raises(AttributeError, match="has not been assigned"):
        field.name


def test_instance_input_access_is_not_constructed_yet() -> None:
    class Inputs(ProcedureInputs):
        value = input(EXAMPLE_ARTIFACT)

    with pytest.raises(AttributeError, match="input values are not constructed yet"):
        Inputs().value


def test_instance_output_access_is_not_constructed_yet() -> None:
    class Outputs(ProcedureOutputs):
        value = output(EXAMPLE_ARTIFACT)

    with pytest.raises(AttributeError, match="output values are not constructed yet"):
        Outputs().value


def test_public_attributes_must_be_io_fields() -> None:
    with pytest.raises(TypeError, match="Inputs.value must be a procedure I/O field"):

        class Inputs(ProcedureInputs):
            value = EXAMPLE_ARTIFACT


def test_plain_attribute_cannot_override_an_inherited_field() -> None:
    class BaseInputs(ProcedureInputs):
        value = input(EXAMPLE_ARTIFACT)

    with pytest.raises(TypeError, match="Inputs.value must be a procedure I/O field"):

        class Inputs(BaseInputs):
            value = None  # type: ignore[assignment]


def test_same_field_descriptor_cannot_declare_multiple_names() -> None:
    field = input(EXAMPLE_ARTIFACT)

    with pytest.raises(TypeError, match="field descriptor cannot be reused"):

        class Inputs(ProcedureInputs):
            first = field
            second = field


def test_field_descriptor_cannot_be_reused_by_another_record() -> None:
    field = input(EXAMPLE_ARTIFACT)

    class FirstInputs(ProcedureInputs):
        first = field

    with pytest.raises(TypeError, match="field descriptor cannot be reused"):

        class SecondInputs(ProcedureInputs):
            second = field

    assert FirstInputs.first.name == "first"


def test_annotation_only_public_attributes_are_rejected() -> None:
    with pytest.raises(TypeError, match="Inputs.value must be a procedure I/O field"):

        class Inputs(ProcedureInputs):
            value: object


def test_private_and_initialized_annotations_are_not_fields() -> None:
    class Inputs(ProcedureInputs):
        _metadata: object
        value: object = input(EXAMPLE_ARTIFACT)

    assert list(Inputs.fields) == ["value"]


def test_field_artifact_must_be_an_artifact_definition() -> None:
    with pytest.raises(TypeError, match="artifact must be an ArtifactDefinition"):
        input(object())  # type: ignore[arg-type]


def test_io_field_metadata_is_immutable() -> None:
    class Inputs(ProcedureInputs):
        value = input(EXAMPLE_ARTIFACT)

    with pytest.raises(AttributeError):
        Inputs.value.direction = "output"  # type: ignore[misc]


def test_mixed_direction_inheritance_is_rejected() -> None:
    class Outputs(ProcedureOutputs):
        value = output(EXAMPLE_ARTIFACT)

    with pytest.raises(TypeError, match="Inputs.value must be an input field"):

        class Inputs(ProcedureInputs, Outputs):
            pass


def test_record_direction_cannot_be_overridden() -> None:
    with pytest.raises(TypeError, match="I/O record direction cannot be overridden"):

        class Inputs(ProcedureInputs):
            _direction = "output"
            value = output(EXAMPLE_ARTIFACT)


def test_inherited_field_can_be_compatibly_overridden() -> None:
    class BaseInputs(ProcedureInputs):
        value = input(EXAMPLE_ARTIFACT, description="Base description.")

    class Inputs(BaseInputs):
        value = input(EXAMPLE_ARTIFACT, description="Specialized description.")

    assert Inputs.value.description == "Specialized description."
    assert list(Inputs.fields) == ["value"]


def test_inherited_field_cannot_change_artifact() -> None:
    class BaseInputs(ProcedureInputs):
        value = input(EXAMPLE_ARTIFACT)

    with pytest.raises(TypeError, match="Inputs.value cannot change artifact"):

        class Inputs(BaseInputs):
            value = input(OTHER_ARTIFACT)


def test_multiple_inheritance_preserves_base_order() -> None:
    class LeftInputs(ProcedureInputs):
        left = input(EXAMPLE_ARTIFACT)

    class RightInputs(ProcedureInputs):
        right = input(EXAMPLE_ARTIFACT)

    class Inputs(LeftInputs, RightInputs):
        local = input(EXAMPLE_ARTIFACT)

    assert list(Inputs.fields) == ["left", "right", "local"]


def test_conflicting_inherited_fields_require_an_explicit_override() -> None:
    class LeftInputs(ProcedureInputs):
        value = input(EXAMPLE_ARTIFACT)

    class RightInputs(ProcedureInputs):
        value = input(OTHER_ARTIFACT)

    with pytest.raises(
        TypeError, match="Inputs.value has conflicting inherited fields"
    ):

        class Inputs(LeftInputs, RightInputs):
            pass


def test_explicit_override_resolves_inherited_field_conflict() -> None:
    class LeftInputs(ProcedureInputs):
        value = input(EXAMPLE_ARTIFACT)

    class RightInputs(ProcedureInputs):
        value = input(OTHER_ARTIFACT)

    class Inputs(LeftInputs, RightInputs):
        value = input(EXAMPLE_ARTIFACT)

    assert Inputs.fields["value"] is Inputs.value
