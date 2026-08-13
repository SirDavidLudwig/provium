"""Generic typed artifact definitions and lazy provider resolution."""

from __future__ import annotations

from collections.abc import Callable
from os import PathLike
from typing import Any, ClassVar, cast, overload

from ..context import current_context
from .reader import ArtifactReader
from .writer import ArtifactWriter


def artifact_class_identifier(artifact: type[Artifact]) -> str:
    """Return the default persistent identifier for an artifact class."""
    return f"{artifact.__module__}.{artifact.__qualname__}"


class Artifact[ReaderT: ArtifactReader, WriterT: ArtifactWriter]:
    """Bind a logical artifact type to its concrete reader and writer types."""

    reader: type[ReaderT] | Callable[[], type[ReaderT]]
    writer: type[WriterT] | Callable[[], type[WriterT]]
    _reader_type_cache: ClassVar[type[ArtifactReader] | None] = None
    _writer_type_cache: ClassVar[type[ArtifactWriter] | None] = None

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        cls._reader_type_cache = None
        cls._writer_type_cache = None

    @classmethod
    def _resolve_reader(cls) -> type[ReaderT]:
        cached = cls._reader_type_cache
        if cached is not None:
            return cast(type[ReaderT], cached)
        provider = getattr(cls, "reader", None)
        candidate = (
            provider
            if isinstance(provider, type)
            else provider()
            if callable(provider)
            else None
        )
        if not isinstance(candidate, type) or not issubclass(candidate, ArtifactReader):
            raise TypeError("reader provider must resolve to an ArtifactReader type")
        cls._reader_type_cache = candidate
        return cast(type[ReaderT], candidate)

    @classmethod
    def _resolve_writer(cls) -> type[WriterT]:
        cached = cls._writer_type_cache
        if cached is not None:
            return cast(type[WriterT], cached)
        provider = getattr(cls, "writer", None)
        candidate = (
            provider
            if isinstance(provider, type)
            else provider()
            if callable(provider)
            else None
        )
        if not isinstance(candidate, type) or not issubclass(candidate, ArtifactWriter):
            raise TypeError("writer provider must resolve to an ArtifactWriter type")
        cls._writer_type_cache = candidate
        return cast(type[WriterT], candidate)

    @classmethod
    def open(cls, path: str | PathLike[str]) -> ReaderT:
        context = current_context()
        if context is None:
            raise RuntimeError("artifact I/O requires an active execution context")
        opener = getattr(context, "open_artifact", None)
        if not callable(opener):
            raise TypeError("active context does not support artifact opening")
        return cast(ReaderT, opener(cls, path, cls._resolve_reader()))

    @classmethod
    def create(cls, path: str | PathLike[str]) -> WriterT:
        context = current_context()
        if context is None:
            raise RuntimeError("artifact I/O requires an active execution context")
        creator = getattr(context, "create_artifact", None)
        if not callable(creator):
            raise TypeError("active context does not support artifact creating")
        return cast(WriterT, creator(cls, path, cls._resolve_writer()))


__all__ = ["Artifact", "artifact_class_identifier"]


@overload
def open_artifact(path: str | PathLike[str]) -> ArtifactReader: ...


@overload
def open_artifact[ReaderT: ArtifactReader, WriterT: ArtifactWriter](
    path: str | PathLike[str],
    *,
    expected: type[Artifact[ReaderT, WriterT]],
) -> ReaderT: ...


@overload
def open_artifact(
    path: str | PathLike[str],
    *,
    expected: tuple[type[Artifact], ...],
) -> ArtifactReader: ...


def open_artifact(
    path: str | PathLike[str],
    *,
    expected: type[Artifact] | tuple[type[Artifact], ...] | None = None,
) -> ArtifactReader:
    """Open an artifact whose concrete type will be discovered from its header."""
    context = current_context()
    if context is None:
        raise RuntimeError("artifact I/O requires an active execution context")
    opener = getattr(context, "open_unknown_artifact", None)
    if not callable(opener):
        raise TypeError("active context does not support artifact opening")
    expected_types = None
    if expected is not None:
        expected_types = expected if isinstance(expected, tuple) else (expected,)
    return cast(ArtifactReader, opener(path, expected_types))


__all__.append("open_artifact")
