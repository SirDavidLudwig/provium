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


class OtherReader(ArtifactReader):
    pass


class OtherWriter(ArtifactWriter):
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


@pytest.mark.parametrize("binding_type", [ArtifactReadBinding, ArtifactWriteBinding])
def test_direct_binding_construction_normalizes_paths(
    binding_type: type[object],
) -> None:
    binding = binding_type(ExampleArtifact, "artifact.pa")  # type: ignore[call-arg]

    assert binding.path == Path("artifact.pa")  # type: ignore[attr-defined]


@pytest.mark.parametrize("binding_type", [ArtifactReadBinding, ArtifactWriteBinding])
def test_direct_binding_construction_rejects_invalid_artifacts(
    binding_type: type[object],
) -> None:
    with pytest.raises(TypeError, match="artifact must be an Artifact class"):
        binding_type(object(), Path("artifact.pa"))  # type: ignore[call-arg]


@pytest.mark.parametrize("binding_type", [ArtifactReadBinding, ArtifactWriteBinding])
def test_direct_binding_construction_rejects_invalid_paths(
    binding_type: type[object],
) -> None:
    with pytest.raises(TypeError, match="path must be a string or path-like object"):
        binding_type(ExampleArtifact, object())  # type: ignore[call-arg]


class IncompleteArtifact(Artifact[Reader, Writer]):
    pass


class InvalidDefinitionArtifact(Artifact[Reader, Writer]):
    definition = object()  # type: ignore[assignment]
    reader = Reader
    writer = Writer


class InvalidReaderArtifact(Artifact[Reader, Writer]):
    definition = ExampleArtifact.definition
    reader = object  # type: ignore[assignment]
    writer = Writer


class InvalidWriterArtifact(Artifact[Reader, Writer]):
    definition = ExampleArtifact.definition
    reader = Reader
    writer = object  # type: ignore[assignment]


class MismatchedReaderArtifact(Artifact[Reader, Writer]):
    definition = ExampleArtifact.definition
    reader = OtherReader  # type: ignore[assignment]
    writer = Writer


class MismatchedWriterArtifact(Artifact[Reader, Writer]):
    definition = ExampleArtifact.definition
    reader = Reader
    writer = OtherWriter  # type: ignore[assignment]


class OtherSpecializationArtifact(Artifact[OtherReader, OtherWriter]):
    definition = ExampleArtifact.definition
    reader = OtherReader
    writer = OtherWriter


class AmbiguousArtifact(ExampleArtifact, OtherSpecializationArtifact):
    definition = ExampleArtifact.definition
    reader = Reader
    writer = Writer


class UnspecializedArtifact[ReaderT: ArtifactReader](Artifact[ReaderT, Writer]):
    definition = ExampleArtifact.definition
    reader = Reader  # type: ignore[assignment]
    writer = Writer


class InvalidDumpArtifact(Artifact[Reader, Writer]):
    definition = ExampleArtifact.definition
    reader = Reader
    writer = Writer
    dump = object()  # type: ignore[assignment]


class InvalidLoadArtifact(Artifact[Reader, Writer]):
    definition = ExampleArtifact.definition
    reader = Reader
    writer = Writer
    load = object()  # type: ignore[assignment]


@pytest.mark.parametrize(
    ("artifact", "message"),
    [
        (Artifact, "definition"),
        (IncompleteArtifact, "definition"),
        (InvalidDefinitionArtifact, "definition"),
        (InvalidReaderArtifact, "reader"),
        (InvalidWriterArtifact, "writer"),
        (MismatchedReaderArtifact, "reader does not match"),
        (MismatchedWriterArtifact, "writer does not match"),
        (AmbiguousArtifact, "exactly one generic specialization"),
        (UnspecializedArtifact, "exactly one generic specialization"),
        (InvalidDumpArtifact, "dump must be callable or None"),
        (InvalidLoadArtifact, "load must be callable or None"),
    ],
)
def test_bindings_reject_nonconcrete_artifact_classes(
    artifact: type[object], message: str
) -> None:
    with pytest.raises(TypeError, match=message):
        ArtifactReadBinding(artifact, Path("artifact.pa"))  # type: ignore[arg-type]
