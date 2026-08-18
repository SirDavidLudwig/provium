"""Typed artifact definitions and path binding."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import cast, overload

from ..context import current_context, current_execution_context
from .reader import ArtifactReader
from .writer import ArtifactWriter


def _path(value: str | PathLike[str]) -> Path:
    if not isinstance(value, (str, PathLike)):
        raise TypeError("artifact path must be a string or path-like object")
    return Path(value)


@dataclass(frozen=True, slots=True, eq=False)
class Artifact[ReaderT: ArtifactReader, WriterT: ArtifactWriter]:
    """An immutable artifact reader and writer implementation."""

    identifier: str
    label: str
    reader: type[ReaderT]
    writer: type[WriterT]
    dump: Callable[[ReaderT, Path], None] | None = None
    load: Callable[[Path, WriterT], None] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.identifier, str) or not self.identifier:
            raise ValueError("artifact identifier must be a non-empty string")
        if not isinstance(self.label, str) or not self.label:
            raise ValueError("artifact label must be a non-empty string")
        if not isinstance(self.reader, type) or not issubclass(
            self.reader, ArtifactReader
        ):
            raise TypeError("artifact reader must be an ArtifactReader type")
        if not isinstance(self.writer, type) or not issubclass(
            self.writer, ArtifactWriter
        ):
            raise TypeError("artifact writer must be an ArtifactWriter type")
        if self.dump is not None and not callable(self.dump):
            raise TypeError("artifact dump must be callable")
        if self.load is not None and not callable(self.load):
            raise TypeError("artifact load must be callable")

    def open(self, path: str | PathLike[str]) -> ReaderT:
        artifact_path = _path(path)
        context = current_context()
        if context is None:
            raise RuntimeError(
                "artifact opening requires an active session or execution context"
            )
        opener = getattr(context, "open_artifact", None)
        if not callable(opener):
            raise TypeError("active context does not support artifact opening")
        return cast(ReaderT, opener(self, artifact_path, self.reader))

    def create(self, path: str | PathLike[str]) -> WriterT:
        artifact_path = _path(path)
        context = current_execution_context() or current_context()
        if context is None:
            raise RuntimeError("artifact creation requires an active execution context")
        creator = getattr(context, "create_artifact", None)
        if not callable(creator):
            raise TypeError("active context does not support artifact creating")
        return cast(WriterT, creator(self, artifact_path, self.writer))

    def bind_read(
        self, path: str | PathLike[str]
    ) -> BoundReadArtifact[ReaderT, WriterT]:
        return BoundReadArtifact(self, _path(path))

    def bind_write(
        self, path: str | PathLike[str]
    ) -> BoundWriteArtifact[ReaderT, WriterT]:
        return BoundWriteArtifact(self, _path(path))


@dataclass(frozen=True, slots=True)
class BoundReadArtifact[ReaderT: ArtifactReader, WriterT: ArtifactWriter]:
    artifact: Artifact[ReaderT, WriterT]
    path: Path

    def open(self) -> ReaderT:
        return self.artifact.open(self.path)


@dataclass(frozen=True, slots=True)
class BoundWriteArtifact[ReaderT: ArtifactReader, WriterT: ArtifactWriter]:
    artifact: Artifact[ReaderT, WriterT]
    path: Path

    def open(self) -> WriterT:
        return self.artifact.create(self.path)


@overload
def open_artifact(path: str | PathLike[str]) -> ArtifactReader: ...


@overload
def open_artifact[ReaderT: ArtifactReader, WriterT: ArtifactWriter](
    path: str | PathLike[str],
    *,
    expected: Artifact[ReaderT, WriterT],
) -> ReaderT: ...


@overload
def open_artifact(
    path: str | PathLike[str],
    *,
    expected: tuple[Artifact, ...],
) -> ArtifactReader: ...


def open_artifact(
    path: str | PathLike[str],
    *,
    expected: Artifact | tuple[Artifact, ...] | None = None,
) -> ArtifactReader:
    """Open an artifact whose concrete type will be discovered from its header."""
    artifact_path = _path(path)
    context = current_context()
    if context is None:
        raise RuntimeError(
            "artifact opening requires an active session or execution context"
        )
    opener = getattr(context, "open_unknown_artifact", None)
    if not callable(opener):
        raise TypeError("active context does not support artifact opening")
    expected_types = None
    if expected is not None:
        expected_types = expected if isinstance(expected, tuple) else (expected,)
    return cast(ArtifactReader, opener(artifact_path, expected_types))


__all__ = [
    "Artifact",
    "BoundReadArtifact",
    "BoundWriteArtifact",
    "open_artifact",
]
