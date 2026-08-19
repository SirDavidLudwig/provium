"""Lazy artifact definitions and their explicit discovery catalog."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from importlib import import_module
from types import MappingProxyType
from typing import cast

from .definition import Artifact


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")


@dataclass(frozen=True, slots=True)
class ArtifactDefinition[ArtifactT: Artifact]:
    """Describe an artifact implementation without importing it eagerly."""

    identifier: str
    target: str
    description: str

    def __post_init__(self) -> None:
        _require_text(self.identifier, "artifact definition identifier")
        _require_text(self.target, "artifact definition target")
        _require_text(self.description, "artifact definition description")
        module_name, separator, attribute_path = self.target.partition(":")
        if not separator or not module_name or not attribute_path:
            raise ValueError(
                "artifact definition target must use 'module:attribute' syntax"
            )

    def resolve(self) -> ArtifactT:
        """Import, validate, and return the targeted artifact instance."""
        module_name, _, attribute_path = self.target.partition(":")
        resolved: object = import_module(module_name)
        for component in attribute_path.split("."):
            resolved = getattr(resolved, component)
        if not isinstance(resolved, Artifact):
            raise TypeError("artifact definition target must resolve to an Artifact")
        if resolved.identifier != self.identifier:
            raise ValueError(
                "resolved artifact identifier does not match its definition"
            )
        return cast(ArtifactT, resolved)


class ArtifactCatalog:
    """Map persistent identifiers to lazily resolved artifact definitions."""

    def __init__(self) -> None:
        self._definitions: dict[str, ArtifactDefinition] = {}

    def register[ArtifactT: Artifact](
        self, definition: ArtifactDefinition[ArtifactT]
    ) -> ArtifactDefinition[ArtifactT]:
        if not isinstance(definition, ArtifactDefinition):
            raise TypeError("catalog entries must be ArtifactDefinition instances")
        if definition.identifier in self._definitions:
            raise ValueError(
                f"artifact identifier is already registered: {definition.identifier}"
            )
        self._definitions[definition.identifier] = definition
        return definition

    def resolve(self, identifier: str) -> ArtifactDefinition:
        return self._definitions[identifier]

    @property
    def definitions(self) -> Mapping[str, ArtifactDefinition]:
        return MappingProxyType(self._definitions)


__all__ = ["ArtifactCatalog", "ArtifactDefinition"]
