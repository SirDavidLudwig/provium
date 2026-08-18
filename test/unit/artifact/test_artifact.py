from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from os import PathLike
from pathlib import Path

import pytest

from provium import Artifact, ArtifactReader, ArtifactWriter, open_artifact
from provium.context import activate_context


class ExampleReader(ArtifactReader):
    pass


class ExampleWriter(ArtifactWriter):
    pass


Example = Artifact("example.ExampleV1", "Example", ExampleReader, ExampleWriter)


@dataclass
class FakeContext:
    active: bool = True
    calls: list[tuple[str, Artifact, object, type[object]]] = field(
        default_factory=list
    )

    def open_artifact(
        self,
        artifact: Artifact,
        path: str | PathLike[str],
        reader_type: type[ArtifactReader],
    ) -> ArtifactReader:
        self.calls.append(("open", artifact, path, reader_type))
        return object.__new__(reader_type)

    def create_artifact(
        self,
        artifact: Artifact,
        path: str | PathLike[str],
        writer_type: type[ArtifactWriter],
    ) -> ArtifactWriter:
        self.calls.append(("create", artifact, path, writer_type))
        return object.__new__(writer_type)


@contextmanager
def fake_context() -> Generator[FakeContext]:
    context = FakeContext()
    with activate_context(context):
        yield context


def test_artifact_opens_and_creates_its_native_types() -> None:
    with fake_context() as context:
        reader = Example.open("input.pa")
        writer = Example.create(Path("output.pa"))

    assert isinstance(reader, ExampleReader)
    assert isinstance(writer, ExampleWriter)
    assert context.calls == [
        ("open", Example, Path("input.pa"), ExampleReader),
        ("create", Example, Path("output.pa"), ExampleWriter),
    ]


def test_bound_artifact_opens_in_its_bound_mode() -> None:
    read = Example.bind_read("input.pa")
    write = Example.bind_write(Path("output.pa"))

    with fake_context() as context:
        reader = read.open()
        writer = write.open()

    assert isinstance(reader, ExampleReader)
    assert isinstance(writer, ExampleWriter)
    assert read.artifact is Example
    assert read.path == Path("input.pa")
    assert write.artifact is Example
    assert write.path == Path("output.pa")
    assert context.calls == [
        ("open", Example, Path("input.pa"), ExampleReader),
        ("create", Example, Path("output.pa"), ExampleWriter),
    ]


@pytest.mark.parametrize("path", [b"data", object(), 42])
def test_binding_requires_an_explicit_filesystem_path(path: object) -> None:
    with pytest.raises(TypeError, match="path"):
        Example.bind_read(path)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="path"):
        Example.bind_write(path)  # type: ignore[arg-type]


@pytest.mark.parametrize("operation", ["open", "create"])
def test_direct_io_requires_an_explicit_filesystem_path(operation: str) -> None:
    with fake_context(), pytest.raises(TypeError, match="path"):
        getattr(Example, operation)(b"artifact.pa")


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (("", "Example", ExampleReader, ExampleWriter), "identifier"),
        ((42, "Example", ExampleReader, ExampleWriter), "identifier"),
        (("example.V1", "", ExampleReader, ExampleWriter), "label"),
        (("example.V1", 42, ExampleReader, ExampleWriter), "label"),
        (("example.V1", "Example", object, ExampleWriter), "reader"),
        (("example.V1", "Example", 42, ExampleWriter), "reader"),
        (("example.V1", "Example", ExampleReader, object), "writer"),
        (("example.V1", "Example", ExampleReader, 42), "writer"),
    ],
)
def test_artifact_validates_its_definition(
    arguments: tuple[object, object, object, object], message: str
) -> None:
    with pytest.raises((TypeError, ValueError), match=message):
        Artifact(*arguments)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("keywords", "error_type", "message"),
    [
        ({"dump": 42}, TypeError, "dump"),
        ({"load": 42}, TypeError, "load"),
    ],
)
def test_artifact_validates_optional_details(
    keywords: dict[str, object], error_type: type[Exception], message: str
) -> None:
    with pytest.raises(error_type, match=message):
        Artifact(
            "example.ExampleV1",
            "Example",
            reader=ExampleReader,
            writer=ExampleWriter,
            **keywords,  # type: ignore[arg-type]
        )


def test_artifact_io_requires_a_compatible_active_context() -> None:
    with pytest.raises(RuntimeError, match="execution context"):
        Example.open("input.pa")
    with pytest.raises(RuntimeError, match="execution context"):
        Example.create("output.pa")
    with activate_context(object()), pytest.raises(TypeError, match="opening"):
        Example.open("input.pa")
    with activate_context(object()), pytest.raises(TypeError, match="creating"):
        Example.create("output.pa")
    with activate_context(object()), pytest.raises(TypeError, match="opening"):
        open_artifact("input.pa")
