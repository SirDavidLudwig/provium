"""Base type for artifact implementations."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import ClassVar


def _require_text(value: object, field_name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value.strip():
        raise ValueError(f"{field_name} must be nonempty")


def _is_dotted_identifier(value: str) -> bool:
    return all(component.isidentifier() for component in value.split("."))


@dataclass(frozen=True, slots=True)
class ArtifactDefinition:
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

    def resolve(self) -> type[Artifact]:
        """Import and validate the artifact class described by this definition."""
        module_name, _, attribute_path = self.target.partition(":")
        resolved: object = import_module(module_name)
        for component in attribute_path.split("."):
            resolved = getattr(resolved, component)

        if not isinstance(resolved, type) or not issubclass(resolved, Artifact):
            raise TypeError(
                "artifact definition target must resolve to an Artifact class"
            )
        resolved_definition = getattr(resolved, "definition", None)
        if not isinstance(resolved_definition, ArtifactDefinition):
            raise TypeError(
                "resolved Artifact class definition must be an ArtifactDefinition"
            )
        if resolved_definition != self:
            raise ValueError("resolved artifact definition does not match its target")
        return resolved


class Artifact[ReaderT, WriterT]:
    """An artifact implementation with specialized reader and writer types."""

    definition: ClassVar[ArtifactDefinition]


__all__ = ["Artifact", "ArtifactDefinition"]
