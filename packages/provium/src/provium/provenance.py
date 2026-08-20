"""Immutable provenance value records and canonical serialization."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, ClassVar, Self, cast


def _require_text(value: object, field_name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _json_object(value: str) -> Mapping[str, Any]:
    decoded = json.loads(value)
    if not isinstance(decoded, Mapping):
        raise TypeError("serialized provenance record must be a JSON object")
    return cast(Mapping[str, Any], decoded)


class _SerializableRecord:
    _shape_name: ClassVar[str]

    def to_json(self) -> str:
        """Serialize this record to canonical JSON."""
        return _canonical_json(cast(Any, self).to_dict())

    @classmethod
    def from_json(cls, value: str) -> Self:
        """Deserialize this record from a JSON object."""
        return cast(Self, cast(Any, cls).from_dict(_json_object(value)))

    @classmethod
    def _expect_keys(cls, value: Mapping[str, Any], keys: set[str]) -> None:
        if not isinstance(value, Mapping) or set(value) != keys:
            raise ValueError(f"invalid {cls._shape_name}")


@dataclass(frozen=True, slots=True)
class ArtifactReference(_SerializableRecord):
    """The persistent identity and catalog type of an artifact."""

    identity: str
    artifact_identifier: str
    _shape_name: ClassVar[str] = "artifact reference"

    def __post_init__(self) -> None:
        _require_text(self.identity, "identity")
        _require_text(self.artifact_identifier, "artifact_identifier")

    def to_dict(self) -> dict[str, str]:
        return {
            "artifact_identifier": self.artifact_identifier,
            "identity": self.identity,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        cls._expect_keys(value, {"artifact_identifier", "identity"})
        return cls(value["identity"], value["artifact_identifier"])


@dataclass(frozen=True, slots=True)
class ArtifactRecord(_SerializableRecord):
    """A finalized artifact digest and its producing execution."""

    reference: ArtifactReference
    body_digest: str
    producer_execution_identity: str
    _shape_name: ClassVar[str] = "artifact record"

    def __post_init__(self) -> None:
        if not isinstance(self.reference, ArtifactReference):
            raise TypeError("reference must be an artifact reference")
        _require_text(self.body_digest, "body_digest")
        _require_text(
            self.producer_execution_identity,
            "producer_execution_identity",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "body_digest": self.body_digest,
            "producer_execution_identity": self.producer_execution_identity,
            "reference": self.reference.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        cls._expect_keys(
            value,
            {"body_digest", "producer_execution_identity", "reference"},
        )
        return cls(
            ArtifactReference.from_dict(value["reference"]),
            value["body_digest"],
            value["producer_execution_identity"],
        )


@dataclass(frozen=True, slots=True)
class ProcedureRecord(_SerializableRecord):
    """A procedure identity and its optional configuration snapshot."""

    name: str
    version: str
    config: Any = None
    config_codec: str | None = None
    _shape_name: ClassVar[str] = "procedure record"

    def __post_init__(self) -> None:
        _require_text(self.name, "name")
        _require_text(self.version, "version")
        if self.config_codec is not None:
            _require_text(self.config_codec, "config_codec")

    def to_dict(self) -> dict[str, Any]:
        return {
            "config": self.config,
            "config_codec": self.config_codec,
            "name": self.name,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        cls._expect_keys(value, {"config", "config_codec", "name", "version"})
        return cls(
            value["name"],
            value["version"],
            value["config"],
            value["config_codec"],
        )


@dataclass(frozen=True, slots=True)
class ProcedureExecutionRecord(_SerializableRecord):
    """One procedure execution and its artifact edges."""

    identity: str
    procedure: ProcedureRecord
    inputs: tuple[ArtifactReference, ...] = ()
    outputs: tuple[ArtifactReference, ...] = ()
    _shape_name: ClassVar[str] = "procedure execution record"

    def __post_init__(self) -> None:
        _require_text(self.identity, "identity")
        if not isinstance(self.procedure, ProcedureRecord):
            raise TypeError("procedure must be a procedure record")
        if not self.outputs:
            raise ValueError("a procedure execution requires at least one output")
        self._validate_references(self.inputs, "input")
        self._validate_references(self.outputs, "output")
        self._validate_edge_directions()
        object.__setattr__(self, "inputs", self._normalized(self.inputs))
        object.__setattr__(self, "outputs", self._normalized(self.outputs))

    @staticmethod
    def _validate_references(
        references: tuple[ArtifactReference, ...],
        kind: str,
    ) -> None:
        if any(not isinstance(item, ArtifactReference) for item in references):
            raise TypeError(f"{kind} must contain artifact references")
        identities = [item.identity for item in references]
        if len(identities) != len(set(identities)):
            raise ValueError(f"duplicate {kind} artifact identity")

    @staticmethod
    def _normalized(
        references: tuple[ArtifactReference, ...],
    ) -> tuple[ArtifactReference, ...]:
        return tuple(sorted(references, key=lambda item: item.identity))

    def _validate_edge_directions(self) -> None:
        input_identities = {reference.identity for reference in self.inputs}
        output_identities = {reference.identity for reference in self.outputs}
        if input_identities & output_identities:
            raise ValueError("artifact cannot be both an input and an output")

    def to_dict(self) -> dict[str, Any]:
        return {
            "identity": self.identity,
            "inputs": [reference.to_dict() for reference in self.inputs],
            "outputs": [reference.to_dict() for reference in self.outputs],
            "procedure": self.procedure.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        cls._expect_keys(value, {"identity", "inputs", "outputs", "procedure"})
        return cls(
            value["identity"],
            ProcedureRecord.from_dict(value["procedure"]),
            tuple(ArtifactReference.from_dict(item) for item in value["inputs"]),
            tuple(ArtifactReference.from_dict(item) for item in value["outputs"]),
        )


__all__ = [
    "ArtifactRecord",
    "ArtifactReference",
    "ProcedureExecutionRecord",
    "ProcedureRecord",
]
