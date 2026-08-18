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
    aliases: tuple[str, ...] = ()


class ArtifactCatalog:
    """Map canonical identifiers and aliases to typed artifact definitions."""

    def __init__(self) -> None:
        self._identifiers: dict[str, ArtifactRegistration] = {}
        self._artifacts: dict[Artifact, ArtifactRegistration] = {}

    def register(
        self,
        canonical_identifier: str,
        artifact: Artifact,
        *,
        aliases: tuple[str, ...] = (),
    ) -> ArtifactRegistration:
        _require_identifier(canonical_identifier, "canonical identifier")
        if not isinstance(artifact, Artifact):
            raise TypeError("artifact must be an Artifact instance")
        for alias in aliases:
            _require_identifier(alias, "alias")
        if len(aliases) != len(set(aliases)):
            raise ValueError("duplicate alias in registration")
        if canonical_identifier in aliases:
            raise ValueError("alias must differ from the canonical identifier")
        if canonical_identifier in self._identifiers:
            raise ValueError(
                f"canonical identifier is already registered: {canonical_identifier}"
            )
        if artifact in self._artifacts:
            raise ValueError("artifact is already registered")
        for alias in aliases:
            if alias in self._identifiers:
                raise ValueError(f"alias is already registered: {alias}")

        registration = ArtifactRegistration(canonical_identifier, artifact, aliases)
        self._identifiers[canonical_identifier] = registration
        self._identifiers.update((alias, registration) for alias in aliases)
        self._artifacts[artifact] = registration
        return registration

    def resolve(self, identifier: str) -> ArtifactRegistration:
        return self._identifiers[identifier]

    def registration_for(self, artifact: Artifact) -> ArtifactRegistration:
        return self._artifacts[artifact]

    @property
    def registrations(self) -> Mapping[str, ArtifactRegistration]:
        """Canonical registrations keyed by canonical identifier."""
        return MappingProxyType(
            {
                registration.canonical_identifier: registration
                for registration in self._artifacts.values()
            }
        )


__all__ = ["ArtifactCatalog", "ArtifactRegistration"]
