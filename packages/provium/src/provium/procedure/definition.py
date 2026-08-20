"""Lightweight procedure contracts and definitions."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Any, ClassVar, cast


def _require_text(value: object, field_name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value.strip():
        raise ValueError(f"{field_name} must be nonempty")


def _is_dotted_identifier(value: str) -> bool:
    return all(component.isidentifier() for component in value.split("."))


class ProcedureInputs:
    """Base type for a procedure's declared input record."""


class ProcedureOutputs:
    """Base type for a procedure's declared output record."""


class ProcedureContract[ConfigT]:
    """Lightweight configuration and I/O contract for a procedure."""

    configuration: ClassVar[type[object] | None] = None

    class SetupInputs(ProcedureInputs):
        pass

    class Inputs(ProcedureInputs):
        pass

    class Outputs(ProcedureOutputs):
        pass


class Procedure[ConfigT, SetupInputsT, InputsT, OutputsT]:
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
