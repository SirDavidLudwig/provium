"""Tests for typed artifact path bindings."""

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from provium import (
    Artifact,
    ArtifactDefinition,
    ArtifactReadBinding,
    ArtifactReader,
    ArtifactWriteBinding,
    ArtifactWriter,
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


def test_artifact_binds_a_normalized_read_path() -> None:
    binding = ExampleArtifact.bind_read("nested/input.pa")

    assert binding == ArtifactReadBinding(ExampleArtifact, Path("nested/input.pa"))
    assert binding.artifact is ExampleArtifact
    assert binding.path == Path("nested/input.pa")


def test_artifact_binds_a_normalized_write_path() -> None:
    binding = ExampleArtifact.bind_write(Path("nested/output.pa"))

    assert binding == ArtifactWriteBinding(ExampleArtifact, Path("nested/output.pa"))
    assert binding.artifact is ExampleArtifact
    assert binding.path == Path("nested/output.pa")


def test_bindings_are_immutable() -> None:
    read = ExampleArtifact.bind_read("input.pa")
    write = ExampleArtifact.bind_write("output.pa")

    with pytest.raises(FrozenInstanceError):
        read.path = Path("changed.pa")
    with pytest.raises(FrozenInstanceError):
        write.path = Path("changed.pa")


@pytest.mark.parametrize("method_name", ["bind_read", "bind_write"])
def test_artifact_binding_rejects_non_path_values(method_name: str) -> None:
    method = getattr(ExampleArtifact, method_name)

    with pytest.raises(TypeError):
        method(object())
