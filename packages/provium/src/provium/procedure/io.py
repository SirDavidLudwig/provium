"""Declarative procedure input and output fields."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
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

    __slots__ = (
        "_artifact",
        "_description",
        "_direction",
        "_maximum",
        "_minimum",
        "_name",
        "_owner",
    )

    def __init__(
        self,
        artifact: ArtifactDefinition[Any],
        direction: Literal["input", "output"],
        description: str | None,
        *,
        minimum: int = 1,
        maximum: int | None = 1,
    ) -> None:
        if not isinstance(artifact, ArtifactDefinition):
            raise TypeError(
                "procedure I/O field artifact must be an ArtifactDefinition"
            )
        if direction not in ("input", "output"):
            raise ValueError("procedure I/O field direction must be input or output")
        if description is not None and not isinstance(description, str):
            raise TypeError("procedure I/O field description must be a string")
        if description is not None and not description.strip():
            raise ValueError("procedure I/O field description must be nonempty")
        if type(minimum) is not int:
            raise TypeError("procedure I/O field minimum must be an integer")
        if minimum < 0:
            raise ValueError("procedure I/O field minimum must be nonnegative")
        if maximum is not None and type(maximum) is not int:
            raise TypeError("procedure I/O field maximum must be an integer or None")
        if maximum is not None and maximum < minimum:
            raise ValueError(
                "procedure I/O field maximum must be greater than or equal to minimum"
            )
        self._name: str | None = None
        self._owner: type[object] | None = None
        self._artifact: ArtifactDefinition[Any] = artifact
        self._direction: Literal["input", "output"] = direction
        self._description: str | None = description
        self._minimum = minimum
        self._maximum = maximum

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
        return self._minimum

    @property
    def maximum(self) -> int | None:
        """Return the permitted maximum number of bindings."""
        return self._maximum

    @property
    def required(self) -> bool:
        """Return whether the field requires a binding."""
        return self._minimum > 0

    @property
    def repeated(self) -> bool:
        """Return whether the field contains several ordered bindings."""
        return False


class ProcedureInputField[ReaderT: ArtifactReader](ProcedureIOField):
    """A required input field whose instance value will be a read binding."""

    __slots__ = ()

    def __init__[WriterT: ArtifactWriter](
        self,
        artifact: ArtifactDefinition[Artifact[ReaderT, WriterT]],
        *,
        description: str | None = None,
    ) -> None:
        super().__init__(artifact, "input", description)

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

    def __init__[ReaderT: ArtifactReader](
        self,
        artifact: ArtifactDefinition[Artifact[ReaderT, WriterT]],
        *,
        description: str | None = None,
    ) -> None:
        super().__init__(artifact, "output", description)

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


class ProcedureOptionalInputField[ReaderT: ArtifactReader](ProcedureIOField):
    """An optional input field whose instance value may be absent."""

    __slots__ = ()

    def __init__[WriterT: ArtifactWriter](
        self,
        artifact: ArtifactDefinition[Artifact[ReaderT, WriterT]],
        *,
        description: str | None = None,
    ) -> None:
        super().__init__(artifact, "input", description, minimum=0)

    @overload
    def __get__(
        self, instance: None, owner: type[object]
    ) -> ProcedureOptionalInputField[ReaderT]: ...

    @overload
    def __get__(
        self, instance: object, owner: type[object] | None = None
    ) -> ArtifactReadBinding[ReaderT] | None: ...

    def __get__(
        self, instance: object | None, owner: type[object] | None = None
    ) -> Any:
        if instance is None:
            return self
        raise AttributeError("procedure input values are not constructed yet")


class ProcedureOptionalOutputField[WriterT: ArtifactWriter](ProcedureIOField):
    """An optional output field whose instance value may be absent."""

    __slots__ = ()

    def __init__[ReaderT: ArtifactReader](
        self,
        artifact: ArtifactDefinition[Artifact[ReaderT, WriterT]],
        *,
        description: str | None = None,
    ) -> None:
        super().__init__(artifact, "output", description, minimum=0)

    @overload
    def __get__(
        self, instance: None, owner: type[object]
    ) -> ProcedureOptionalOutputField[WriterT]: ...

    @overload
    def __get__(
        self, instance: object, owner: type[object] | None = None
    ) -> ArtifactWriteBinding[WriterT] | None: ...

    def __get__(
        self, instance: object | None, owner: type[object] | None = None
    ) -> Any:
        if instance is None:
            return self
        raise AttributeError("procedure output values are not constructed yet")


class ProcedureRepeatedInputField[ReaderT: ArtifactReader](ProcedureIOField):
    """A repeated input field whose instance value is an ordered tuple."""

    __slots__ = ()

    def __init__[WriterT: ArtifactWriter](
        self,
        artifact: ArtifactDefinition[Artifact[ReaderT, WriterT]],
        *,
        minimum: int = 0,
        maximum: int | None = None,
        description: str | None = None,
    ) -> None:
        super().__init__(
            artifact,
            "input",
            description,
            minimum=minimum,
            maximum=maximum,
        )

    @property
    def repeated(self) -> bool:
        """Return whether the field contains several ordered bindings."""
        return True

    @overload
    def __get__(
        self, instance: None, owner: type[object]
    ) -> ProcedureRepeatedInputField[ReaderT]: ...

    @overload
    def __get__(
        self, instance: object, owner: type[object] | None = None
    ) -> tuple[ArtifactReadBinding[ReaderT], ...]: ...

    def __get__(
        self, instance: object | None, owner: type[object] | None = None
    ) -> Any:
        if instance is None:
            return self
        raise AttributeError("procedure input values are not constructed yet")


class _ProcedureIORecord:
    _direction: ClassVar[Literal["input", "output"]]
    fields: ClassVar[Mapping[str, ProcedureIOField]] = MappingProxyType({})

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        cls._validate_direction_declaration()
        fields, inherited_candidates, conflicts = cls._collect_inherited_fields()
        cls._merge_declared_fields(fields, inherited_candidates, conflicts)
        cls._validate_undeclared_annotations()
        cls._validate_collected_fields(fields, conflicts)
        cls.fields = MappingProxyType(fields)

    @classmethod
    def _validate_direction_declaration(cls) -> None:
        if "_direction" in cls.__dict__ and _ProcedureIORecord not in cls.__bases__:
            raise TypeError("procedure I/O record direction cannot be overridden")

    @classmethod
    def _collect_inherited_fields(
        cls,
    ) -> tuple[
        dict[str, ProcedureIOField],
        dict[str, list[ProcedureIOField]],
        set[str],
    ]:
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
        return fields, inherited_candidates, conflicts

    @classmethod
    def _merge_declared_fields(
        cls,
        fields: dict[str, ProcedureIOField],
        inherited_candidates: Mapping[str, list[ProcedureIOField]],
        conflicts: set[str],
    ) -> None:
        local_field_ids: set[int] = set()
        for name, value in cls.__dict__.items():
            if name.startswith("_"):
                continue
            value = cls._validate_declared_field(name, value, local_field_ids)
            cls._validate_field_override(
                name,
                value,
                inherited_candidates.get(name, ()),
            )
            fields[name] = value
            conflicts.discard(name)

    @classmethod
    def _validate_declared_field(
        cls,
        name: str,
        value: object,
        local_field_ids: set[int],
    ) -> ProcedureIOField:
        if not isinstance(value, ProcedureIOField):
            raise TypeError(f"{cls.__name__}.{name} must be a procedure I/O field")
        if not callable(getattr(type(value), "__get__", None)):
            raise TypeError(
                f"{cls.__name__}.{name} must use a concrete procedure I/O field"
            )
        if not value.is_declared_on(cls) or id(value) in local_field_ids:
            raise TypeError("procedure I/O field descriptor cannot be reused")
        local_field_ids.add(id(value))
        return value

    @classmethod
    def _validate_field_override(
        cls,
        name: str,
        value: ProcedureIOField,
        inherited: Sequence[ProcedureIOField],
    ) -> None:
        inherited_artifacts = {
            (candidate.artifact.identifier, candidate.artifact.target)
            for candidate in inherited
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

        inherited_cardinalities = {
            (candidate.minimum, candidate.maximum) for candidate in inherited
        }
        if (
            inherited_cardinalities
            and (
                value.minimum,
                value.maximum,
            )
            not in inherited_cardinalities
        ):
            raise TypeError(f"{cls.__name__}.{name} cannot change cardinality")

        inherited_shapes = {candidate.repeated for candidate in inherited}
        if inherited_shapes and value.repeated not in inherited_shapes:
            raise TypeError(f"{cls.__name__}.{name} cannot change binding shape")

    @classmethod
    def _validate_undeclared_annotations(cls) -> None:
        annotations = cls.__dict__.get("__annotations__", {})
        for name in annotations:
            if not name.startswith("_") and name not in cls.__dict__:
                raise TypeError(f"{cls.__name__}.{name} must be a procedure I/O field")

    @classmethod
    def _validate_collected_fields(
        cls,
        fields: Mapping[str, ProcedureIOField],
        conflicts: set[str],
    ) -> None:
        for name, field in fields.items():
            if name in conflicts:
                raise TypeError(
                    f"{cls.__name__}.{name} has conflicting inherited fields"
                )
            if field.direction != cls._direction:
                raise TypeError(
                    f"{cls.__name__}.{name} must be an {cls._direction} field"
                )


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
    return ProcedureInputField(artifact, description=description)


def output[ReaderT: ArtifactReader, WriterT: ArtifactWriter](
    artifact: ArtifactDefinition[Artifact[ReaderT, WriterT]],
    *,
    description: str | None = None,
) -> ProcedureOutputField[WriterT]:
    """Declare one required procedure output."""
    return ProcedureOutputField(artifact, description=description)


def optional_input[ReaderT: ArtifactReader, WriterT: ArtifactWriter](
    artifact: ArtifactDefinition[Artifact[ReaderT, WriterT]],
    *,
    description: str | None = None,
) -> ProcedureOptionalInputField[ReaderT]:
    """Declare one optional procedure input."""
    return ProcedureOptionalInputField(artifact, description=description)


def optional_output[ReaderT: ArtifactReader, WriterT: ArtifactWriter](
    artifact: ArtifactDefinition[Artifact[ReaderT, WriterT]],
    *,
    description: str | None = None,
) -> ProcedureOptionalOutputField[WriterT]:
    """Declare one optional procedure output."""
    return ProcedureOptionalOutputField(artifact, description=description)


def repeated_input[ReaderT: ArtifactReader, WriterT: ArtifactWriter](
    artifact: ArtifactDefinition[Artifact[ReaderT, WriterT]],
    *,
    minimum: int = 0,
    maximum: int | None = None,
    description: str | None = None,
) -> ProcedureRepeatedInputField[ReaderT]:
    """Declare an ordered collection of procedure inputs."""
    return ProcedureRepeatedInputField(
        artifact,
        minimum=minimum,
        maximum=maximum,
        description=description,
    )


__all__ = [
    "ProcedureIOField",
    "ProcedureInputField",
    "ProcedureInputs",
    "ProcedureOptionalInputField",
    "ProcedureOptionalOutputField",
    "ProcedureOutputField",
    "ProcedureOutputs",
    "ProcedureRepeatedInputField",
    "input",
    "optional_input",
    "optional_output",
    "output",
    "repeated_input",
]
