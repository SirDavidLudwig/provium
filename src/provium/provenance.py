"""Dependency-free provenance value models and normalized lineage graphs."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, ClassVar, Self


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")


def _object_from_json(value: str) -> dict[str, Any]:
    decoded = json.loads(value)
    if not isinstance(decoded, dict):
        raise TypeError("serialized model must be a JSON object")
    return decoded


def _json(data: Mapping[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class _Serializable:
    _shape_name: ClassVar[str]

    def to_dict(self) -> dict[str, Any]:  # pragma: no cover - interface declaration
        raise NotImplementedError

    @classmethod
    def from_dict(  # pragma: no cover - interface declaration
        cls, value: Mapping[str, Any]
    ) -> Self:
        raise NotImplementedError

    def to_json(self) -> str:
        return _json(self.to_dict())

    @classmethod
    def from_json(cls, value: str) -> Self:
        return cls.from_dict(_object_from_json(value))

    @classmethod
    def _expect_keys(cls, value: Mapping[str, Any], keys: set[str]) -> None:
        if not isinstance(value, Mapping) or set(value) != keys:
            raise ValueError(f"invalid {cls._shape_name}")


@dataclass(frozen=True, slots=True)
class ArtifactReference(_Serializable):
    """The catalog type and persistent identity of an artifact."""

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
        cls._expect_keys(value, {"identity", "artifact_identifier"})
        return cls(
            identity=value["identity"], artifact_identifier=value["artifact_identifier"]
        )


@dataclass(frozen=True, slots=True)
class ArtifactRecord(_Serializable):
    """An artifact together with its finalized content digest and producer."""

    reference: ArtifactReference
    body_digest: str
    producer_execution_identity: str
    _shape_name: ClassVar[str] = "artifact record"

    def __post_init__(self) -> None:
        if not isinstance(self.reference, ArtifactReference):
            raise TypeError("reference must be an artifact reference")
        _require_text(self.body_digest, "body_digest")
        _require_text(self.producer_execution_identity, "producer_execution_identity")

    def to_dict(self) -> dict[str, Any]:
        return {
            "body_digest": self.body_digest,
            "producer_execution_identity": self.producer_execution_identity,
            "reference": self.reference.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        cls._expect_keys(
            value, {"reference", "body_digest", "producer_execution_identity"}
        )
        return cls(
            reference=ArtifactReference.from_dict(value["reference"]),
            body_digest=value["body_digest"],
            producer_execution_identity=value["producer_execution_identity"],
        )


@dataclass(frozen=True, slots=True)
class ProcedureRecord(_Serializable):
    """An immutable description and optional configuration snapshot of a procedure."""

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
        cls._expect_keys(value, {"name", "version", "config", "config_codec"})
        return cls(
            name=value["name"],
            version=value["version"],
            config=value["config"],
            config_codec=value["config_codec"],
        )


@dataclass(frozen=True, slots=True)
class ProcedureExecutionRecord(_Serializable):
    """One execution and the artifact edges observed during it."""

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
        object.__setattr__(
            self, "inputs", tuple(sorted(self.inputs, key=lambda item: item.identity))
        )
        object.__setattr__(
            self, "outputs", tuple(sorted(self.outputs, key=lambda item: item.identity))
        )

    @staticmethod
    def _validate_references(
        references: tuple[ArtifactReference, ...], kind: str
    ) -> None:
        if any(
            not isinstance(reference, ArtifactReference) for reference in references
        ):
            raise ValueError(f"{kind} must contain artifact references")
        identities = [reference.identity for reference in references]
        if len(identities) != len(set(identities)):
            raise ValueError(f"duplicate {kind} artifact identity")

    def to_dict(self) -> dict[str, Any]:
        return {
            "identity": self.identity,
            "inputs": [reference.to_dict() for reference in self.inputs],
            "outputs": [reference.to_dict() for reference in self.outputs],
            "procedure": self.procedure.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        cls._expect_keys(value, {"identity", "procedure", "inputs", "outputs"})
        return cls(
            identity=value["identity"],
            procedure=ProcedureRecord.from_dict(value["procedure"]),
            inputs=tuple(ArtifactReference.from_dict(item) for item in value["inputs"]),
            outputs=tuple(
                ArtifactReference.from_dict(item) for item in value["outputs"]
            ),
        )


@dataclass(frozen=True, slots=True)
class ArtifactLineage(_Serializable):
    """A normalized, mergeable DAG of artifacts and their producing executions."""

    artifacts: Mapping[str, ArtifactRecord] = field(default_factory=dict)
    executions: Mapping[str, ProcedureExecutionRecord] = field(default_factory=dict)
    _shape_name: ClassVar[str] = "artifact lineage"

    def __post_init__(self) -> None:
        artifacts = dict(self.artifacts)
        executions = dict(self.executions)
        for identity, record in artifacts.items():
            if identity != record.reference.identity:
                raise ValueError("artifact map key does not match artifact identity")
            execution = executions.get(record.producer_execution_identity)
            if execution is None:
                raise ValueError(
                    f"artifact {identity!r} has a missing producer execution"
                )
            if record.reference not in execution.outputs:
                raise ValueError(
                    f"artifact {identity!r} is not an output of its producer execution"
                )
        for identity, execution in executions.items():
            if identity != execution.identity:
                raise ValueError("execution map key does not match execution identity")
            for reference in (*execution.inputs, *execution.outputs):
                if reference.identity not in artifacts:
                    raise ValueError(
                        f"execution references missing artifact {reference.identity!r}"
                    )
        object.__setattr__(self, "artifacts", MappingProxyType(artifacts))
        object.__setattr__(self, "executions", MappingProxyType(executions))

    @classmethod
    def for_execution(
        cls,
        execution: ProcedureExecutionRecord,
        output_records: tuple[ArtifactRecord, ...],
        input_lineages: tuple[ArtifactLineage, ...] = (),
    ) -> Self:
        lineage = cls._merge_many(input_lineages)
        output_references = {
            reference.identity: reference for reference in execution.outputs
        }
        records = {record.reference.identity: record for record in output_records}
        if set(records) != set(output_references) or any(
            records[identity].reference != reference
            for identity, reference in output_references.items()
        ):
            raise ValueError("output records must exactly match execution outputs")
        if any(
            record.producer_execution_identity != execution.identity
            for record in output_records
        ):
            raise ValueError("output record producer must match the execution")
        missing_inputs = [
            reference.identity
            for reference in execution.inputs
            if lineage._record_for(reference) is None
        ]
        if missing_inputs:
            raise ValueError(
                f"input artifact is absent from input lineage: {missing_inputs[0]}"
            )
        artifacts = dict(lineage.artifacts)
        artifacts.update(records)
        executions = dict(lineage.executions)
        if (
            execution.identity in executions
            and executions[execution.identity] != execution
        ):
            raise ValueError(f"execution conflict for identity {execution.identity!r}")
        executions[execution.identity] = execution
        return cls(artifacts, executions)

    @classmethod
    def _merge_many(cls, lineages: tuple[ArtifactLineage, ...]) -> Self:
        result = cls()
        for lineage in lineages:
            result = result.merge(lineage)
        return result

    def _record_for(self, reference: ArtifactReference) -> ArtifactRecord | None:
        record = self.artifacts.get(reference.identity)
        if record is not None and record.reference != reference:
            return None
        return record

    def merge(self, other: ArtifactLineage) -> Self:
        artifacts = dict(self.artifacts)
        executions = dict(self.executions)
        for identity, record in other.artifacts.items():
            if identity in artifacts and artifacts[identity] != record:
                raise ValueError(f"artifact conflict for identity {identity!r}")
            artifacts[identity] = record
        for identity, execution in other.executions.items():
            if identity in executions and executions[identity] != execution:
                raise ValueError(f"execution conflict for identity {identity!r}")
            executions[identity] = execution
        return type(self)(artifacts, executions)

    def artifact(self, reference: ArtifactReference) -> ArtifactRecord:
        record = self.artifacts[reference.identity]
        if record.reference != reference:
            raise ValueError("artifact reference does not match the stored artifact")
        return record

    def producing_execution(
        self, reference: ArtifactReference
    ) -> ProcedureExecutionRecord:
        return self.executions[self.artifact(reference).producer_execution_identity]

    def ancestry(self, reference: ArtifactReference) -> Self:
        artifacts: dict[str, ArtifactRecord] = {}
        executions: dict[str, ProcedureExecutionRecord] = {}

        def visit(current: ArtifactReference) -> None:
            record = self.artifact(current)
            if current.identity in artifacts:
                return
            artifacts[current.identity] = record
            execution = self.executions[record.producer_execution_identity]
            executions[execution.identity] = execution
            for input_reference in execution.inputs:
                visit(input_reference)
            for output_reference in execution.outputs:
                artifacts[output_reference.identity] = self.artifact(output_reference)

        visit(reference)
        return type(self)(artifacts, executions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifacts": [
                self.artifacts[key].to_dict() for key in sorted(self.artifacts)
            ],
            "executions": [
                self.executions[key].to_dict() for key in sorted(self.executions)
            ],
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        cls._expect_keys(value, {"artifacts", "executions"})
        if not isinstance(value["artifacts"], list) or not isinstance(
            value["executions"], list
        ):
            raise TypeError("invalid artifact lineage")
        artifacts = [ArtifactRecord.from_dict(item) for item in value["artifacts"]]
        executions = [
            ProcedureExecutionRecord.from_dict(item) for item in value["executions"]
        ]
        return cls(
            {record.reference.identity: record for record in artifacts},
            {execution.identity: execution for execution in executions},
        )


__all__ = [
    "ArtifactLineage",
    "ArtifactRecord",
    "ArtifactReference",
    "ProcedureExecutionRecord",
    "ProcedureRecord",
]
