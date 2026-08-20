"""Immutable metadata returned by completed procedure executions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from provium.provenance import ArtifactLineage, ArtifactReference, ProcedureRecord


@dataclass(frozen=True, slots=True)
class ProcedureExecutionResult:
    """Describe one completed invocation and its named artifact outputs."""

    identity: str
    procedure: ProcedureRecord | None
    inputs: tuple[ArtifactReference, ...]
    outputs: Mapping[str, ArtifactReference] = field(
        default_factory=dict[str, ArtifactReference]
    )
    lineage: ArtifactLineage = field(default_factory=ArtifactLineage)

    def __post_init__(self) -> None:
        if not isinstance(self.identity, str):
            raise TypeError("procedure execution result identity must be a string")
        if not self.identity.strip():
            raise ValueError("procedure execution result identity must be nonempty")
        if self.procedure is not None and not isinstance(
            self.procedure, ProcedureRecord
        ):
            raise TypeError(
                "procedure execution result procedure must be a ProcedureRecord or None"
            )
        if not isinstance(self.inputs, tuple):
            raise TypeError("procedure execution result inputs must be a tuple")
        if any(not isinstance(item, ArtifactReference) for item in self.inputs):
            raise TypeError(
                "procedure execution result inputs must be artifact references"
            )
        if not isinstance(self.outputs, Mapping):
            raise TypeError("procedure execution result outputs must be a mapping")
        normalized_outputs = dict(self.outputs)
        for name, reference in normalized_outputs.items():
            if not isinstance(name, str):
                raise TypeError(
                    "procedure execution result output names must be strings"
                )
            if not name.strip():
                raise ValueError(
                    "procedure execution result output names must be nonempty"
                )
            if not isinstance(reference, ArtifactReference):
                raise TypeError(
                    "procedure execution result outputs must be artifact references"
                )
        if not isinstance(self.lineage, ArtifactLineage):
            raise TypeError(
                "procedure execution result lineage must be an ArtifactLineage"
            )
        object.__setattr__(self, "outputs", MappingProxyType(normalized_outputs))


__all__ = ["ProcedureExecutionResult"]
