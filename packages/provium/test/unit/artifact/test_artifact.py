from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from provium import Artifact, ArtifactDefinition, ArtifactReader, ArtifactWriter


class Reader(ArtifactReader):
    pass


class Writer(ArtifactWriter):
    pass


EXAMPLE_DEFINITION = ArtifactDefinition(
    identifier="example.ExampleV1",
    target="example.artifacts:ExampleArtifact",
    description="An example artifact.",
)


class ExampleArtifact(Artifact[Reader, Writer]):
    definition = EXAMPLE_DEFINITION
    reader = Reader
    writer = Writer


def test_artifacts_are_defined_as_specialized_classes() -> None:
    assert issubclass(ExampleArtifact, Artifact)
    assert ExampleArtifact.definition is EXAMPLE_DEFINITION
    assert ExampleArtifact.reader is Reader
    assert ExampleArtifact.writer is Writer


def test_artifact_custom_transfers_are_optional() -> None:
    assert ExampleArtifact.dump is None
    assert ExampleArtifact.load is None


def test_artifact_can_define_custom_dump_and_load_class_methods() -> None:
    calls: list[tuple[str, object, Path]] = []

    class TransferArtifact(ExampleArtifact):
        @classmethod
        def dump(cls, reader: Reader, destination: Path) -> None:
            calls.append(("dump", reader, destination))

        @classmethod
        def load(cls, source: Path, writer: Writer) -> None:
            calls.append(("load", writer, source))

    # Transfer callbacks only require correctly typed instances; construction and
    # resource ownership are covered by the dedicated reader and writer tests.
    reader = object.__new__(Reader)
    writer = object.__new__(Writer)

    TransferArtifact.dump(reader, Path("dump"))
    TransferArtifact.load(Path("dump"), writer)

    assert calls == [
        ("dump", reader, Path("dump")),
        ("load", writer, Path("dump")),
    ]


def test_artifact_definition_describes_a_lazy_artifact_target() -> None:
    assert EXAMPLE_DEFINITION.identifier == "example.ExampleV1"
    assert EXAMPLE_DEFINITION.target == "example.artifacts:ExampleArtifact"
    assert EXAMPLE_DEFINITION.description == "An example artifact."


def test_artifact_definition_is_immutable() -> None:
    with pytest.raises(FrozenInstanceError):
        EXAMPLE_DEFINITION.identifier = "example.ChangedV1"  # type: ignore[misc]


@pytest.mark.parametrize("field", ["identifier", "target", "description"])
def test_artifact_definition_requires_text_fields(field: str) -> None:
    values: dict[str, object] = {
        "identifier": "example.ExampleV1",
        "target": "example.artifacts:ExampleArtifact",
        "description": "An example artifact.",
    }
    values[field] = object()

    with pytest.raises(TypeError, match=field):
        ArtifactDefinition(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize("field", ["identifier", "target", "description"])
@pytest.mark.parametrize("value", ["", "   "])
def test_artifact_definition_requires_nonempty_fields(field: str, value: str) -> None:
    values = {
        "identifier": "example.ExampleV1",
        "target": "example.artifacts:ExampleArtifact",
        "description": "An example artifact.",
    }
    values[field] = value

    with pytest.raises(ValueError, match=field):
        ArtifactDefinition(**values)


@pytest.mark.parametrize(
    "target",
    [
        "example.artifacts",
        ":ExampleArtifact",
        "example.artifacts:",
        "example..artifacts:ExampleArtifact",
        "example.artifacts:.ExampleArtifact",
        "example.artifacts:ExampleArtifact.",
        "example artifacts:ExampleArtifact",
        "example.artifacts:Example Artifact",
        " example.artifacts:ExampleArtifact",
        "example.artifacts:ExampleArtifact ",
    ],
)
def test_artifact_definition_requires_module_attribute_target(target: str) -> None:
    with pytest.raises(ValueError, match="module:attribute"):
        ArtifactDefinition(
            identifier="example.ExampleV1",
            target=target,
            description="An example artifact.",
        )
