"""Declarative procedure input and output fields."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, ClassVar, Literal, overload

from provium.artifact import (
    Artifact,
    ArtifactDefinition,
    ArtifactReadBinding,
    ArtifactReader,
    ArtifactWriteBinding,
    ArtifactWriter,
)


class ProcedureIOField:
    """Shared immutable metadata for a declared procedure I/O field."""

    __slots__ = ("_artifact", "_description", "_direction", "_name", "_owner")

    def __init__(
        self,
        artifact: ArtifactDefinition[Any],
        direction: Literal["input", "output"],
        description: str | None,
    ) -> None:
        if not isinstance(artifact, ArtifactDefinition):
            raise TypeError(
                "procedure I/O field artifact must be an ArtifactDefinition"
            )
        if description is not None and not isinstance(description, str):
            raise TypeError("procedure I/O field description must be a string")
        if description is not None and not description.strip():
            raise ValueError("procedure I/O field description must be nonempty")
        self._name: str | None = None
        self._owner: type[object] | None = None
        self._artifact: ArtifactDefinition[Any] = artifact
        self._direction: Literal["input", "output"] = direction
        self._description: str | None = description

    def __set_name__(self, owner: type[object], name: str) -> None:
        if self._owner is None:
            self._owner = owner
            self._name = name

    def is_declared_on(self, owner: type[object]) -> bool:
        """Return whether this descriptor was first assigned to ``owner``."""
        return self._owner is owner

    @property
    def artifact(self) -> ArtifactDefinition[Any]:
        """Return the artifact definition required by this field."""
        return self._artifact

    @property
    def direction(self) -> Literal["input", "output"]:
        """Return whether this field reads an input or writes an output."""
        return self._direction

    @property
    def description(self) -> str | None:
        """Return the optional human-readable field description."""
        return self._description

    @property
    def name(self) -> str:
        """Return the attribute name assigned by the declaring class."""
        if self._name is None:
            raise AttributeError("procedure I/O field has not been assigned to a class")
        return self._name

    @property
    def minimum(self) -> int:
        """Return the required minimum number of bindings."""
        return 1

    @property
    def maximum(self) -> int:
        """Return the permitted maximum number of bindings."""
        return 1

    @property
    def required(self) -> bool:
        """Return whether the field requires a binding."""
        return True


class ProcedureInputField[ReaderT: ArtifactReader](ProcedureIOField):
    """A required input field whose instance value will be a read binding."""

    __slots__ = ()

    @overload
    def __get__(
        self, instance: None, owner: type[object]
    ) -> ProcedureInputField[ReaderT]: ...

    @overload
    def __get__(
        self, instance: object, owner: type[object] | None = None
    ) -> ArtifactReadBinding[ReaderT]: ...

    def __get__(
        self, instance: object | None, owner: type[object] | None = None
    ) -> Any:
        if instance is None:
            return self
        raise AttributeError("procedure input values are not constructed yet")


class ProcedureOutputField[WriterT: ArtifactWriter](ProcedureIOField):
    """A required output field whose instance value will be a write binding."""

    __slots__ = ()

    @overload
    def __get__(
        self, instance: None, owner: type[object]
    ) -> ProcedureOutputField[WriterT]: ...

    @overload
    def __get__(
        self, instance: object, owner: type[object] | None = None
    ) -> ArtifactWriteBinding[WriterT]: ...

    def __get__(
        self, instance: object | None, owner: type[object] | None = None
    ) -> Any:
        if instance is None:
            return self
        raise AttributeError("procedure output values are not constructed yet")


class _ProcedureIORecord:
    _direction: ClassVar[Literal["input", "output"]]
    fields: ClassVar[Mapping[str, ProcedureIOField]] = MappingProxyType({})

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if "_direction" in cls.__dict__ and _ProcedureIORecord not in cls.__bases__:
            raise TypeError("procedure I/O record direction cannot be overridden")

        fields: dict[str, ProcedureIOField] = {}
        inherited_candidates: dict[str, list[ProcedureIOField]] = {}
        for base in cls.__bases__:
            for name, field in getattr(base, "fields", {}).items():
                fields.setdefault(name, field)
                inherited_candidates.setdefault(name, []).append(field)
        conflicts = {
            name
            for name, candidates in inherited_candidates.items()
            if len({id(candidate) for candidate in candidates}) > 1
        }

        local_field_ids: set[int] = set()
        for name, value in cls.__dict__.items():
            if name.startswith("_"):
                continue
            if not isinstance(value, ProcedureIOField):
                raise TypeError(f"{cls.__name__}.{name} must be a procedure I/O field")
            if not value.is_declared_on(cls):
                raise TypeError("procedure I/O field descriptor cannot be reused")
            if id(value) in local_field_ids:
                raise TypeError("procedure I/O field descriptor cannot be reused")
            local_field_ids.add(id(value))
            inherited_artifacts = {
                (candidate.artifact.identifier, candidate.artifact.target)
                for candidate in inherited_candidates.get(name, ())
            }
            if (
                inherited_artifacts
                and (
                    value.artifact.identifier,
                    value.artifact.target,
                )
                not in inherited_artifacts
            ):
                raise TypeError(f"{cls.__name__}.{name} cannot change artifact")
            fields[name] = value
            conflicts.discard(name)

        annotations = cls.__dict__.get("__annotations__", {})
        for name in annotations:
            if not name.startswith("_") and name not in cls.__dict__:
                raise TypeError(f"{cls.__name__}.{name} must be a procedure I/O field")

        for name, field in fields.items():
            if name in conflicts:
                raise TypeError(
                    f"{cls.__name__}.{name} has conflicting inherited fields"
                )
            if field.direction != cls._direction:
                raise TypeError(
                    f"{cls.__name__}.{name} must be an {cls._direction} field"
                )

        cls.fields = MappingProxyType(fields)


class ProcedureInputs(_ProcedureIORecord):
    """Base type for a procedure's declared input record."""

    _direction = "input"


class ProcedureOutputs(_ProcedureIORecord):
    """Base type for a procedure's declared output record."""

    _direction = "output"


def input[ReaderT: ArtifactReader, WriterT: ArtifactWriter](
    artifact: ArtifactDefinition[Artifact[ReaderT, WriterT]],
    *,
    description: str | None = None,
) -> ProcedureInputField[ReaderT]:
    """Declare one required procedure input."""
    return ProcedureInputField(artifact, "input", description)


def output[ReaderT: ArtifactReader, WriterT: ArtifactWriter](
    artifact: ArtifactDefinition[Artifact[ReaderT, WriterT]],
    *,
    description: str | None = None,
) -> ProcedureOutputField[WriterT]:
    """Declare one required procedure output."""
    return ProcedureOutputField(artifact, "output", description)


__all__ = [
    "ProcedureIOField",
    "ProcedureInputField",
    "ProcedureInputs",
    "ProcedureOutputField",
    "ProcedureOutputs",
    "input",
    "output",
]
