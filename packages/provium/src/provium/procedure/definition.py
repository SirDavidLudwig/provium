"""Lightweight procedure contracts and definitions."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Any, ClassVar, cast, get_args, get_origin

from .config import ProcedureConfig
from .io import ProcedureInputs, ProcedureOutputs


def _require_text(value: object, field_name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value.strip():
        raise ValueError(f"{field_name} must be nonempty")


def _is_dotted_identifier(value: str) -> bool:
    return all(component.isidentifier() for component in value.split("."))


class ProcedureContract[ConfigT: ProcedureConfig | None]:
    """Lightweight configuration and I/O contract for a procedure."""

    configuration: type[ConfigT] | None = None
    SetupInputs: ClassVar[type[ProcedureInputs]] = ProcedureInputs
    Inputs: ClassVar[type[ProcedureInputs]] = ProcedureInputs
    Outputs: ClassVar[type[ProcedureOutputs]] = ProcedureOutputs

    def __init_subclass__(cls, **kwargs: Any) -> None:
        # Validate the declaration here so a malformed plugin fails
        # while it is imported, rather than later during procedure execution.
        super().__init_subclass__(**kwargs)
        configuration = cls.configuration
        if configuration is not None and (
            not isinstance(configuration, type)
            or not issubclass(configuration, ProcedureConfig)
        ):
            raise TypeError(
                "procedure contract configuration must be a ProcedureConfig "
                "class or None"
            )
        for name in ("SetupInputs", "Inputs"):
            value = getattr(cls, name)
            if not isinstance(value, type) or not issubclass(value, ProcedureInputs):
                raise TypeError(
                    f"procedure contract {name} must be a ProcedureInputs class"
                )
        outputs = cls.Outputs
        if not isinstance(outputs, type) or not issubclass(outputs, ProcedureOutputs):
            raise TypeError(
                "procedure contract Outputs must be a ProcedureOutputs class"
            )

        # Ensure the runtime configuration agrees with the contract's generic
        # type, including inherited specializations (the concrete ConfigT in
        # ProcedureContract[ConfigT]).
        specializations: set[type[object]] = set()
        for base in cls.__mro__:
            for generic_base in getattr(base, "__orig_bases__", ()):
                if get_origin(generic_base) is ProcedureContract:
                    arguments = get_args(generic_base)
                    # A remaining TypeVar means this is still a generic helper
                    # class, not a concrete contract usable by the executor.
                    if len(arguments) == 1 and isinstance(arguments[0], type):
                        specializations.add(arguments[0])
        if len(specializations) != 1:
            raise TypeError(
                "procedure contract must have exactly one generic specialization"
            )
        expected_configuration = next(iter(specializations))

        # ProcedureContract[None] is represented at runtime by NoneType, while
        # its declaration stores the value None. Configured contracts instead
        # store the exact model class named by their generic specialization.
        if (
            configuration is None
            and expected_configuration is not type(None)
            or configuration is not None
            and configuration is not expected_configuration
        ):
            raise TypeError(
                "procedure contract configuration does not match its generic "
                "specialization"
            )


class Procedure[
    ConfigT: ProcedureConfig | None,
    SetupInputsT: ProcedureInputs,
    InputsT: ProcedureInputs,
    OutputsT: ProcedureOutputs,
]:
    """Base type for a concrete procedure implementation."""

    definition: ClassVar[ProcedureDefinition[Any]]


@dataclass(frozen=True, slots=True)
class ProcedureDefinition[ProcedureT: Procedure[Any, Any, Any, Any]]:
    """Describe a procedure implementation without importing it eagerly."""

    identifier: str
    target: str
    label: str
    description: str | None
    contract: type[ProcedureContract[Any]]

    def __post_init__(self) -> None:
        _require_text(self.identifier, "procedure definition identifier")
        _require_text(self.target, "procedure definition target")
        _require_text(self.label, "procedure definition label")
        if self.description is not None:
            _require_text(self.description, "procedure definition description")
        if not isinstance(self.contract, type) or not issubclass(
            self.contract, ProcedureContract
        ):
            raise TypeError(
                "procedure definition contract must be a ProcedureContract class"
            )

        module_name, separator, attribute_path = self.target.partition(":")
        if (
            not separator
            or not _is_dotted_identifier(module_name)
            or not _is_dotted_identifier(attribute_path)
            or ":" in attribute_path
        ):
            raise ValueError(
                "procedure definition target must use 'module:attribute' syntax"
            )

    def resolve(self) -> type[ProcedureT]:
        """Import and return the procedure class described by this definition."""
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
                "resolved procedure definition identifier and target do not match"
            )
        return cast(type[ProcedureT], resolved)


__all__ = [
    "Procedure",
    "ProcedureContract",
    "ProcedureDefinition",
    "ProcedureInputs",
    "ProcedureOutputs",
]
