"""Immutable typed artifact path bindings."""

from __future__ import annotations

from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast, get_args, get_origin

from .reader import ArtifactReader
from .writer import ArtifactWriter

if TYPE_CHECKING:
    from .definition import Artifact


def validate_artifact_class(artifact: object) -> type[Artifact[Any, Any]]:
    """Validate and return one concrete class-based artifact implementation."""
    from .definition import Artifact, ArtifactDefinition

    if not isinstance(artifact, type) or not issubclass(artifact, Artifact):
        raise TypeError("artifact binding artifact must be an Artifact class")
    artifact_class = cast(type[object], artifact)
    if not isinstance(getattr(artifact_class, "definition", None), ArtifactDefinition):
        raise TypeError("artifact binding artifact must declare an artifact definition")
    reader = getattr(artifact_class, "reader", None)
    if not isinstance(reader, type) or not issubclass(reader, ArtifactReader):
        raise TypeError(
            "artifact binding artifact must declare an artifact reader class"
        )
    writer = getattr(artifact_class, "writer", None)
    if not isinstance(writer, type) or not issubclass(writer, ArtifactWriter):
        raise TypeError(
            "artifact binding artifact must declare an artifact writer class"
        )
    specializations: set[tuple[type[object], type[object]]] = set()
    for base in artifact_class.__mro__:
        for generic_base in getattr(base, "__orig_bases__", ()):
            if get_origin(generic_base) is Artifact:
                arguments = get_args(generic_base)
                if len(arguments) == 2 and all(
                    isinstance(argument, type) for argument in arguments
                ):
                    specializations.add(
                        cast(tuple[type[object], type[object]], arguments)
                    )
    if len(specializations) != 1:
        raise TypeError(
            "artifact binding artifact must have exactly one generic specialization"
        )
    expected_reader, expected_writer = next(iter(specializations))
    if reader is not expected_reader:
        raise TypeError(
            "artifact binding artifact reader does not match its generic specialization"
        )
    if writer is not expected_writer:
        raise TypeError(
            "artifact binding artifact writer does not match its generic specialization"
        )
    dump = getattr(artifact_class, "dump", None)
    if dump is not None and not callable(dump):
        raise TypeError("artifact binding artifact dump must be callable or None")
    load = getattr(artifact_class, "load", None)
    if load is not None and not callable(load):
        raise TypeError("artifact binding artifact load must be callable or None")
    return cast(type[Artifact[Any, Any]], artifact)


def _validate_binding(artifact: object, path: object) -> Path:
    validate_artifact_class(artifact)
    if not isinstance(path, (str, PathLike)):
        raise TypeError("artifact binding path must be a string or path-like object")
    return Path(cast(str | PathLike[str], path))


@dataclass(frozen=True, slots=True)
class ArtifactReadBinding[ReaderT: ArtifactReader]:
    """Bind a concrete artifact reader type to a filesystem path."""

    artifact: type[Artifact[ReaderT, Any]]
    path: Path

    def __post_init__(self) -> None:
        normalized = _validate_binding(self.artifact, self.path)
        object.__setattr__(self, "path", normalized)


@dataclass(frozen=True, slots=True)
class ArtifactWriteBinding[WriterT: ArtifactWriter]:
    """Bind a concrete artifact writer type to a filesystem path."""

    artifact: type[Artifact[Any, WriterT]]
    path: Path

    def __post_init__(self) -> None:
        normalized = _validate_binding(self.artifact, self.path)
        object.__setattr__(self, "path", normalized)


__all__ = [
    "ArtifactReadBinding",
    "ArtifactWriteBinding",
    "validate_artifact_class",
]
