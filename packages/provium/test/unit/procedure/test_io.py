"""Tests for declarative procedure I/O fields."""

from pathlib import Path

import pytest

from provium import (
    Artifact,
    ArtifactDefinition,
    ArtifactReadBinding,
    ArtifactReader,
    ArtifactWriteBinding,
    ArtifactWriter,
    ProcedureInputField,
    ProcedureInputs,
    ProcedureIOField,
    ProcedureOptionalInputField,
    ProcedureOptionalOutputField,
    ProcedureOutputField,
    ProcedureOutputs,
    ProcedureRepeatedInputField,
    input,
    optional_input,
    optional_output,
    output,
    repeated_input,
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


def test_optional_input_exposes_optional_metadata() -> None:
    class Inputs(ProcedureInputs):
        previous = optional_input(EXAMPLE_ARTIFACT, description="A previous value.")

    assert Inputs.fields["previous"] is Inputs.previous
    assert Inputs.previous.artifact is EXAMPLE_ARTIFACT
    assert Inputs.previous.direction == "input"
    assert Inputs.previous.minimum == 0
    assert Inputs.previous.maximum == 1
    assert Inputs.previous.required is False
    assert Inputs.previous.description == "A previous value."


def test_optional_output_exposes_optional_metadata() -> None:
    class Outputs(ProcedureOutputs):
        preview = optional_output(EXAMPLE_ARTIFACT)

    assert Outputs.fields["preview"] is Outputs.preview
    assert Outputs.preview.artifact is EXAMPLE_ARTIFACT
    assert Outputs.preview.direction == "output"
    assert Outputs.preview.minimum == 0
    assert Outputs.preview.maximum == 1
    assert Outputs.preview.required is False
    assert Outputs.preview.description is None


def test_optional_instance_access_is_not_constructed_yet() -> None:
    class Inputs(ProcedureInputs):
        value = optional_input(EXAMPLE_ARTIFACT)

    class Outputs(ProcedureOutputs):
        value = optional_output(EXAMPLE_ARTIFACT)

    with pytest.raises(AttributeError, match="input values are not constructed yet"):
        Inputs.value.__get__(object(), Inputs)
    with pytest.raises(AttributeError, match="output values are not constructed yet"):
        Outputs.value.__get__(object(), Outputs)


def test_repeated_input_exposes_unbounded_metadata_by_default() -> None:
    class Inputs(ProcedureInputs):
        values = repeated_input(EXAMPLE_ARTIFACT)

    assert Inputs.fields["values"] is Inputs.values
    assert Inputs.values.artifact is EXAMPLE_ARTIFACT
    assert Inputs.values.direction == "input"
    assert Inputs.values.minimum == 0
    assert Inputs.values.maximum is None
    assert Inputs.values.required is False
    assert Inputs.values.repeated is True


def test_repeated_input_exposes_bounded_metadata() -> None:
    class Inputs(ProcedureInputs):
        values = repeated_input(
            EXAMPLE_ARTIFACT,
            minimum=1,
            maximum=32,
            description="The ordered input values.",
        )

    assert Inputs.values.minimum == 1
    assert Inputs.values.maximum == 32
    assert Inputs.values.required is True
    assert Inputs.values.description == "The ordered input values."


def test_repeated_input_instance_access_is_not_constructed_yet() -> None:
    class Inputs(ProcedureInputs):
        values = repeated_input(EXAMPLE_ARTIFACT)

    with pytest.raises(AttributeError, match="input values are not constructed yet"):
        Inputs.values.__get__(object(), Inputs)


def test_outputs_reject_repeated_input_fields() -> None:
    with pytest.raises(TypeError, match="Outputs.values must be an output field"):

        class Outputs(ProcedureOutputs):
            values = repeated_input(EXAMPLE_ARTIFACT)


def test_singular_and_repeated_fields_are_incompatible_overrides() -> None:
    class BaseInputs(ProcedureInputs):
        value = input(EXAMPLE_ARTIFACT)

    with pytest.raises(TypeError, match="Inputs.value cannot change binding shape"):

        class Inputs(BaseInputs):
            value = repeated_input(EXAMPLE_ARTIFACT, minimum=1, maximum=1)


def test_repeated_descriptor_supplies_input_direction() -> None:
    field = ProcedureRepeatedInputField(EXAMPLE_ARTIFACT, minimum=2, maximum=4)

    assert field.direction == "input"
    assert field.minimum == 2
    assert field.maximum == 4
    assert field.repeated is True


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
        Inputs.value.__get__(object(), Inputs)


def test_instance_output_access_is_not_constructed_yet() -> None:
    class Outputs(ProcedureOutputs):
        value = output(EXAMPLE_ARTIFACT)

    with pytest.raises(AttributeError, match="output values are not constructed yet"):
        Outputs.value.__get__(object(), Outputs)


def test_public_attributes_must_be_io_fields() -> None:
    with pytest.raises(TypeError, match="Inputs.value must be a procedure I/O field"):

        class Inputs(ProcedureInputs):
            value = EXAMPLE_ARTIFACT


def test_io_metadata_base_cannot_be_declared_as_a_field() -> None:
    with pytest.raises(TypeError, match="Inputs.value must use a concrete"):

        class Inputs(ProcedureInputs):
            value = ProcedureIOField(EXAMPLE_ARTIFACT, "input", None)


def test_io_field_subclass_must_implement_descriptor_access() -> None:
    class IncompleteField(ProcedureIOField):
        pass

    with pytest.raises(TypeError, match="Inputs.value must use a concrete"):

        class Inputs(ProcedureInputs):
            value = IncompleteField(EXAMPLE_ARTIFACT, "input", None)


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

    with pytest.raises(TypeError, match="conflicting record directions"):

        class Inputs(ProcedureInputs, Outputs):
            pass


def test_empty_mixed_direction_inheritance_is_rejected() -> None:
    with pytest.raises(TypeError, match="conflicting record directions"):

        class Record(ProcedureInputs, ProcedureOutputs):
            pass


def test_unrelated_mixin_direction_does_not_conflict() -> None:
    class Mixin:
        _direction = "output"
        fields = {"foreign": object()}

    class Inputs(ProcedureInputs, Mixin):
        value = input(EXAMPLE_ARTIFACT)

    assert Inputs.value.direction == "input"
    assert list(Inputs.fields) == ["value"]


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


@pytest.mark.parametrize(
    ("base_field", "override_field"),
    [
        (input, optional_input),
        (optional_input, input),
    ],
)
def test_inherited_field_cannot_change_cardinality(
    base_field: object, override_field: object
) -> None:
    class BaseInputs(ProcedureInputs):
        value = base_field(EXAMPLE_ARTIFACT)  # type: ignore[operator]

    with pytest.raises(TypeError, match="Inputs.value cannot change cardinality"):

        class Inputs(BaseInputs):
            value = override_field(EXAMPLE_ARTIFACT)  # type: ignore[operator]


@pytest.mark.parametrize(
    ("direction", "minimum", "maximum", "exception", "message"),
    [
        ("sideways", 1, 1, ValueError, "direction"),
        ("input", True, 1, TypeError, "minimum"),
        ("input", -1, 1, ValueError, "minimum"),
        ("input", 0, True, TypeError, "maximum"),
        ("input", 2, 1, ValueError, "maximum"),
    ],
)
def test_io_field_validates_cardinality_metadata(
    direction: object,
    minimum: object,
    maximum: object,
    exception: type[Exception],
    message: str,
) -> None:
    with pytest.raises(exception, match=message):
        ProcedureIOField(
            EXAMPLE_ARTIFACT,
            direction,  # type: ignore[arg-type]
            None,
            minimum=minimum,  # type: ignore[arg-type]
            maximum=maximum,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("field_type", "direction", "minimum"),
    [
        (ProcedureInputField, "input", 1),
        (ProcedureOutputField, "output", 1),
        (ProcedureOptionalInputField, "input", 0),
        (ProcedureOptionalOutputField, "output", 0),
    ],
)
def test_specialized_field_descriptors_supply_their_own_metadata(
    field_type: type[ProcedureIOField],
    direction: str,
    minimum: int,
) -> None:
    field = field_type(EXAMPLE_ARTIFACT)  # type: ignore[call-arg]

    assert field.direction == direction
    assert field.minimum == minimum
    assert field.maximum == 1


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


def test_records_are_constructed_in_field_order_from_bindings() -> None:
    class Inputs(ProcedureInputs):
        first = input(EXAMPLE_ARTIFACT)
        second = input(EXAMPLE_ARTIFACT)

    first = ArtifactReadBinding(ExampleArtifact, "first.data")
    second = ArtifactReadBinding(ExampleArtifact, "second.data")

    values = Inputs._from_bindings({"second": second, "first": first})

    assert values.first is first
    assert values.second is second
    assert repr(values) == f"Inputs(first={first!r}, second={second!r})"


def test_optional_and_repeated_fields_receive_immutable_defaults() -> None:
    class Inputs(ProcedureInputs):
        previous = optional_input(EXAMPLE_ARTIFACT)
        values = repeated_input(EXAMPLE_ARTIFACT)

    values = Inputs._from_bindings({})

    assert values.previous is None
    assert values.values == ()
    with pytest.raises(AttributeError, match="immutable"):
        values.previous = None  # type: ignore[misc]
    with pytest.raises(AttributeError, match="immutable"):
        del values.values


def test_record_subclasses_do_not_regain_instance_dictionaries() -> None:
    class Inputs(ProcedureInputs):
        value = optional_input(EXAMPLE_ARTIFACT)

    values = Inputs._from_bindings({})

    assert not hasattr(values, "__dict__")


def test_record_subclasses_cannot_explicitly_add_an_instance_dictionary() -> None:
    with pytest.raises(TypeError, match="cannot declare an instance dictionary"):

        class Inputs(ProcedureInputs):
            __slots__ = ("__dict__",)


@pytest.mark.parametrize("method_name", ["__setattr__", "__delattr__"])
def test_record_subclasses_cannot_override_immutability(method_name: str) -> None:
    with pytest.raises(TypeError, match="cannot override record immutability"):
        type(
            "Inputs",
            (ProcedureInputs,),
            {method_name: lambda *args: None},
        )


def test_repeated_inputs_are_normalized_to_an_ordered_tuple() -> None:
    class Inputs(ProcedureInputs):
        values = repeated_input(EXAMPLE_ARTIFACT, minimum=1, maximum=2)

    first = ArtifactReadBinding(ExampleArtifact, "first.data")
    second = ArtifactReadBinding(ExampleArtifact, "second.data")

    values = Inputs._from_bindings({"values": [first, second]})

    assert values.values == (first, second)


def test_output_records_expose_write_bindings() -> None:
    class Outputs(ProcedureOutputs):
        result = output(EXAMPLE_ARTIFACT)
        preview = optional_output(EXAMPLE_ARTIFACT)

    result = ArtifactWriteBinding(ExampleArtifact, "result.data")

    values = Outputs._from_bindings({"result": result})

    assert values.result is result
    assert values.preview is None


def test_record_construction_rejects_unknown_and_missing_fields() -> None:
    class Inputs(ProcedureInputs):
        value = input(EXAMPLE_ARTIFACT)

    with pytest.raises(TypeError, match="unknown field: other"):
        Inputs._from_bindings({"other": object()})
    with pytest.raises(TypeError, match="missing required field: value"):
        Inputs._from_bindings({})
    with pytest.raises(TypeError, match="bindings must be a mapping"):
        Inputs._from_bindings([])  # type: ignore[arg-type]


def test_records_cannot_be_constructed_without_validated_bindings() -> None:
    class Inputs(ProcedureInputs):
        value = optional_input(EXAMPLE_ARTIFACT)

    with pytest.raises(TypeError, match="must be constructed from bindings"):
        Inputs()


@pytest.mark.parametrize("method_name", ["__init__", "_from_bindings"])
def test_record_subclasses_cannot_override_binding_construction(
    method_name: str,
) -> None:
    with pytest.raises(TypeError, match="cannot override binding construction"):
        type("Inputs", (ProcedureInputs,), {method_name: lambda *args: None})


@pytest.mark.parametrize(
    ("record_type", "binding", "message"),
    [
        (
            type("Inputs", (ProcedureInputs,), {"value": input(EXAMPLE_ARTIFACT)}),
            ArtifactWriteBinding(ExampleArtifact, "value.data"),
            "must be an artifact read binding",
        ),
        (
            type("Outputs", (ProcedureOutputs,), {"value": output(EXAMPLE_ARTIFACT)}),
            ArtifactReadBinding(ExampleArtifact, "value.data"),
            "must be an artifact write binding",
        ),
    ],
)
def test_record_construction_rejects_the_wrong_binding_direction(
    record_type: type[ProcedureInputs] | type[ProcedureOutputs],
    binding: object,
    message: str,
) -> None:
    with pytest.raises(TypeError, match=message):
        record_type._from_bindings({"value": binding})


def test_record_construction_rejects_a_different_artifact() -> None:
    class OtherArtifact(Artifact[Reader, Writer]):
        definition = OTHER_ARTIFACT
        reader = Reader
        writer = Writer

    class Inputs(ProcedureInputs):
        value = input(EXAMPLE_ARTIFACT)

    binding = ArtifactReadBinding(OtherArtifact, Path("value.data"))

    with pytest.raises(TypeError, match="value must bind artifact example.ExampleV1"):
        Inputs._from_bindings({"value": binding})


@pytest.mark.parametrize(
    ("supplied", "message"),
    [
        (object(), "must be a sequence of artifact read bindings"),
        ([], "requires at least 1 binding"),
        ([None, None, None], "permits at most 2 bindings"),
        ([None], "must be an artifact read binding"),
    ],
)
def test_repeated_input_construction_validates_shape_and_cardinality(
    supplied: object,
    message: str,
) -> None:
    class Inputs(ProcedureInputs):
        values = repeated_input(EXAMPLE_ARTIFACT, minimum=1, maximum=2)

    with pytest.raises((TypeError, ValueError), match=message):
        Inputs._from_bindings({"values": supplied})
