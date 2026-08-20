"""Base type for artifact implementations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from importlib import import_module
from os import PathLike
from pathlib import Path
from typing import Any, ClassVar, cast

from .binding import ArtifactReadBinding, ArtifactWriteBinding
from .reader import ArtifactReader
from .writer import ArtifactWriter


def _require_text(value: object, field_name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value.strip():
        raise ValueError(f"{field_name} must be nonempty")


def _is_dotted_identifier(value: str) -> bool:
    return all(component.isidentifier() for component in value.split("."))


class Artifact[ReaderT: ArtifactReader, WriterT: ArtifactWriter]:
    """An artifact implementation with specialized reader and writer types."""

    definition: ClassVar[ArtifactDefinition[Any]]
    reader: type[ReaderT]
    writer: type[WriterT]
    dump: Callable[[ReaderT, Path], None] | None = None
    load: Callable[[Path, WriterT], None] | None = None

    @classmethod
    def bind_read(cls, path: str | PathLike[str]) -> ArtifactReadBinding[ReaderT]:
        """Bind this artifact's reader type to a normalized path."""
        return ArtifactReadBinding(cls, Path(path))

    @classmethod
    def bind_write(cls, path: str | PathLike[str]) -> ArtifactWriteBinding[WriterT]:
        """Bind this artifact's writer type to a normalized path."""
        return ArtifactWriteBinding(cls, Path(path))


@dataclass(frozen=True, slots=True)
class ArtifactDefinition[ArtifactT: Artifact[Any, Any]]:
    """Describe an artifact implementation without importing it eagerly."""

    identifier: str
    target: str
    description: str

    def __post_init__(self) -> None:
        _require_text(self.identifier, "artifact definition identifier")
        _require_text(self.target, "artifact definition target")
        _require_text(self.description, "artifact definition description")

        module_name, separator, attribute_path = self.target.partition(":")
        if (
            not separator
            or not _is_dotted_identifier(module_name)
            or not _is_dotted_identifier(attribute_path)
            or ":" in attribute_path
        ):
            raise ValueError(
                "artifact definition target must use 'module:attribute' syntax"
            )

    def resolve(self) -> type[ArtifactT]:
        """Import and return the artifact class described by this definition."""
        module_name, _, attribute_path = self.target.partition(":")
        resolved: object = import_module(module_name)
        for component in attribute_path.split("."):
            resolved = getattr(resolved, component)
        resolved_definition = getattr(resolved, "definition", None)
        if (
            getattr(resolved_definition, "identifier", None) != self.identifier
            or getattr(resolved_definition, "target", None) != self.target
        ):
            raise ValueError(
                "resolved artifact definition identifier and target do not match"
            )
        return cast(type[ArtifactT], resolved)


__all__ = ["Artifact", "ArtifactDefinition"]
