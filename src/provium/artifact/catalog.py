"""Explicit registration of artifact definitions and persistent identifiers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from .definition import Artifact


def _require_identifier(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")


@dataclass(frozen=True, slots=True)
class ArtifactRegistration:
    canonical_identifier: str
    artifact: Artifact


class ArtifactCatalog:
    """Map canonical identifiers to typed artifact definitions."""

    def __init__(self) -> None:
        self._identifiers: dict[str, ArtifactRegistration] = {}
        self._artifacts: dict[Artifact, ArtifactRegistration] = {}

    def register(
        self,
        canonical_identifier: str,
        artifact: Artifact,
    ) -> ArtifactRegistration:
        _require_identifier(canonical_identifier, "canonical identifier")
        if not isinstance(artifact, Artifact):
            raise TypeError("artifact must be an Artifact instance")
        if canonical_identifier in self._identifiers:
            raise ValueError(
                f"canonical identifier is already registered: {canonical_identifier}"
            )
        if artifact in self._artifacts:
            raise ValueError("artifact is already registered")
        registration = ArtifactRegistration(canonical_identifier, artifact)
        self._identifiers[canonical_identifier] = registration
        self._artifacts[artifact] = registration
        return registration

    def resolve(self, identifier: str) -> ArtifactRegistration:
        return self._identifiers[identifier]

    def registration_for(self, artifact: Artifact) -> ArtifactRegistration:
        return self._artifacts[artifact]

    @property
    def registrations(self) -> Mapping[str, ArtifactRegistration]:
        """Canonical registrations keyed by canonical identifier."""
        return MappingProxyType(self._identifiers)


__all__ = ["ArtifactCatalog", "ArtifactRegistration"]
