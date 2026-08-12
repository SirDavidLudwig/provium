from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from os import PathLike

import pytest

from provium import Artifact, ArtifactReader, ArtifactWriter, open_artifact
from provium.context import activate_context


class ExampleReader(ArtifactReader):
    pass


class ExampleWriter(ArtifactWriter):
    pass


@dataclass
class FakeContext:
    active: bool = True
    calls: list[tuple[str, type[Artifact], object, type[object]]] = field(
        default_factory=list
    )

    def open_artifact(
        self,
        artifact: type[Artifact],
        path: str | PathLike[str],
        reader_type: type[ArtifactReader],
    ) -> ArtifactReader:
        self.calls.append(("open", artifact, path, reader_type))
        return object.__new__(reader_type)

    def create_artifact(
        self,
        artifact: type[Artifact],
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


def test_resolves_direct_reader_and_writer_types() -> None:
    class Example(Artifact[ExampleReader, ExampleWriter]):
        reader = ExampleReader
        writer = ExampleWriter

    with fake_context() as context:
        reader = Example.open("input.pa")
        writer = Example.create("output.pa")

    assert isinstance(reader, ExampleReader)
    assert isinstance(writer, ExampleWriter)
    assert context.calls == [
        ("open", Example, "input.pa", ExampleReader),
        ("create", Example, "output.pa", ExampleWriter),
    ]


def test_reader_provider_is_lazy_cached_and_does_not_resolve_writer() -> None:
    calls: list[str] = []

    class Example(Artifact[ExampleReader, ExampleWriter]):
        @staticmethod
        def reader() -> type[ExampleReader]:
            calls.append("reader")
            return ExampleReader

        @staticmethod
        def writer() -> type[ExampleWriter]:
            calls.append("writer")
            return ExampleWriter

    assert calls == []
    with fake_context():
        Example.open("first.pa")
        Example.open("second.pa")
    assert calls == ["reader"]


def test_writer_provider_is_lazy_cached_and_does_not_resolve_reader() -> None:
    calls: list[str] = []

    class Example(Artifact[ExampleReader, ExampleWriter]):
        @staticmethod
        def reader() -> type[ExampleReader]:
            calls.append("reader")
            return ExampleReader

        @staticmethod
        def writer() -> type[ExampleWriter]:
            calls.append("writer")
            return ExampleWriter

    with fake_context():
        Example.create("first.pa")
        Example.create("second.pa")
    assert calls == ["writer"]


@pytest.mark.parametrize(
    ("provider_name", "result"),
    [
        ("reader", object),
        ("reader", ExampleWriter),
        ("reader", 42),
        ("writer", object),
        ("writer", ExampleReader),
        ("writer", 42),
    ],
)
def test_rejects_invalid_provider_results(provider_name: str, result: object) -> None:
    class Example(Artifact[ExampleReader, ExampleWriter]):
        reader = ExampleReader
        writer = ExampleWriter

    setattr(Example, provider_name, staticmethod(lambda: result))

    with fake_context(), pytest.raises(TypeError, match=provider_name):
        if provider_name == "reader":
            Example.open("input.pa")
        else:
            Example.create("output.pa")


def test_rejects_missing_provider() -> None:
    class Missing(Artifact[ExampleReader, ExampleWriter]):
        pass

    with fake_context(), pytest.raises(TypeError, match="reader"):
        Missing.open("input.pa")


def test_artifact_io_requires_a_compatible_active_context() -> None:
    class Example(Artifact[ExampleReader, ExampleWriter]):
        reader = ExampleReader
        writer = ExampleWriter

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
