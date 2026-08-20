"""Lightweight procedure contracts and definitions."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from importlib import import_module
from shlex import quote
from typing import Any, ClassVar, Literal, cast, get_args, get_origin

from .config import ProcedureConfig
from .io import ProcedureInputs, ProcedureIOField, ProcedureOutputs


def _require_text(value: object, field_name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value.strip():
        raise ValueError(f"{field_name} must be nonempty")


def _is_dotted_identifier(value: str) -> bool:
    return all(component.isidentifier() for component in value.split("."))


_CONTRACT_COMPILATION_HOOKS = frozenset(
    {
        "__init_subclass__",
        "_configuration_specialization",
        "_validate_configuration_specialization",
        "_validate_io_declarations",
        "_validated_configuration",
    }
)


@dataclass(frozen=True, slots=True)
class ProcedureIOFieldMetadata:
    """Immutable inspection metadata for one procedure I/O field."""

    name: str
    artifact_identifier: str
    artifact_description: str
    direction: Literal["input", "output"]
    minimum: int
    maximum: int | None
    repeated: bool
    description: str | None

    @property
    def required(self) -> bool:
        """Return whether the field requires at least one binding."""
        return self.minimum > 0


@dataclass(frozen=True, slots=True)
class ProcedureContractMetadata:
    """Immutable, implementation-free metadata compiled from a contract."""

    configuration_target: str | None
    _configuration_schema_json: str | None
    configuration_schema_digest: str | None
    setup_inputs: tuple[ProcedureIOFieldMetadata, ...]
    inputs: tuple[ProcedureIOFieldMetadata, ...]
    outputs: tuple[ProcedureIOFieldMetadata, ...]
    digest: str

    @property
    def configuration_schema(self) -> dict[str, object] | None:
        """Return an isolated, JSON-compatible configuration schema."""
        if self._configuration_schema_json is None:
            return None
        return cast(dict[str, object], json.loads(self._configuration_schema_json))


def _canonical_json(value: object) -> tuple[object, str]:
    encoded = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return json.loads(encoded), sha256(encoded).hexdigest()


def _compile_field_metadata(
    fields: Mapping[str, ProcedureIOField],
) -> tuple[ProcedureIOFieldMetadata, ...]:
    return tuple(
        ProcedureIOFieldMetadata(
            name=name,
            artifact_identifier=field.artifact.identifier,
            artifact_description=field.artifact.description,
            direction=field.direction,
            minimum=field.minimum,
            maximum=field.maximum,
            repeated=field.repeated,
            description=field.description,
        )
        for name, field in fields.items()
    )


def _field_metadata_payload(
    fields: tuple[ProcedureIOFieldMetadata, ...],
) -> list[dict[str, object]]:
    return [
        {
            "name": field.name,
            "artifact_identifier": field.artifact_identifier,
            "artifact_description": field.artifact_description,
            "direction": field.direction,
            "minimum": field.minimum,
            "maximum": field.maximum,
            "repeated": field.repeated,
            "description": field.description,
        }
        for field in fields
    ]


def _compile_contract_metadata(
    configuration: type[ProcedureConfig] | None,
    setup_inputs: type[ProcedureInputs],
    inputs: type[ProcedureInputs],
    outputs: type[ProcedureOutputs],
) -> ProcedureContractMetadata:
    configuration_target: str | None = None
    configuration_schema_json: str | None = None
    configuration_schema_digest: str | None = None
    normalized_schema: object = None
    if configuration is not None:
        configuration_target = (
            f"{configuration.__module__}:{configuration.__qualname__}"
        )
        normalized_schema, configuration_schema_digest = _canonical_json(
            configuration.model_json_schema()
        )
        configuration_schema_json = json.dumps(
            normalized_schema,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    setup_metadata = _compile_field_metadata(setup_inputs.fields)
    input_metadata = _compile_field_metadata(inputs.fields)
    output_metadata = _compile_field_metadata(outputs.fields)
    payload = {
        "configuration_target": configuration_target,
        "configuration_schema": normalized_schema if configuration else None,
        "configuration_schema_digest": configuration_schema_digest,
        "setup_inputs": _field_metadata_payload(setup_metadata),
        "inputs": _field_metadata_payload(input_metadata),
        "outputs": _field_metadata_payload(output_metadata),
    }
    _, digest = _canonical_json(payload)
    return ProcedureContractMetadata(
        configuration_target=configuration_target,
        _configuration_schema_json=configuration_schema_json,
        configuration_schema_digest=configuration_schema_digest,
        setup_inputs=setup_metadata,
        inputs=input_metadata,
        outputs=output_metadata,
        digest=digest,
    )


def _format_binding_argument(
    flag: str,
    field: ProcedureIOFieldMetadata,
) -> str:
    argument = f"{flag} {field.name}=PATH"
    if field.repeated:
        maximum = "unbounded" if field.maximum is None else str(field.maximum)
        ellipsis = " ..." if field.maximum is None or field.maximum > 1 else ""
        repeated_argument = f"{argument}{ellipsis}"
        if not field.required:
            repeated_argument = f"[{repeated_argument}]"
        return f"{repeated_argument} ({field.minimum}..{maximum} bindings)"
    return argument if field.required else f"[{argument}]"


def _invocation_arguments(
    metadata: ProcedureContractMetadata,
) -> list[str]:
    arguments = [
        _format_binding_argument("--setup-input", field)
        for field in metadata.setup_inputs
    ]
    arguments.extend(
        _format_binding_argument("--input", field) for field in metadata.inputs
    )
    arguments.extend(
        _format_binding_argument("--output", field) for field in metadata.outputs
    )
    if metadata.configuration_target is not None:
        arguments.append("[--config FILE ...]")
    return arguments


class ProcedureContract[ConfigT: ProcedureConfig | None]:
    """Lightweight configuration and I/O contract for a procedure."""

    configuration: type[ConfigT] | None = None
    SetupInputs: ClassVar[type[ProcedureInputs]] = ProcedureInputs
    Inputs: ClassVar[type[ProcedureInputs]] = ProcedureInputs
    Outputs: ClassVar[type[ProcedureOutputs]] = ProcedureOutputs
    metadata: ClassVar[ProcedureContractMetadata]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        # Validate the declaration here so a malformed plugin fails
        # while it is imported, rather than later during procedure execution.
        super().__init_subclass__(**kwargs)
        if _CONTRACT_COMPILATION_HOOKS & cls.__dict__.keys():
            raise TypeError("procedure contract cannot override contract compilation")
        configuration = cls._validated_configuration()
        cls._validate_io_declarations()
        cls._validate_configuration_specialization(
            configuration,
            cls._configuration_specialization(),
        )
        cls.metadata = _compile_contract_metadata(
            configuration,
            cls.SetupInputs,
            cls.Inputs,
            cls.Outputs,
        )

    @classmethod
    def _validated_configuration(cls) -> type[ProcedureConfig] | None:
        configuration = cls.configuration
        if configuration is not None and (
            not isinstance(configuration, type)
            or not issubclass(configuration, ProcedureConfig)
        ):
            raise TypeError(
                "procedure contract configuration must be a ProcedureConfig "
                "class or None"
            )
        return cast(type[ProcedureConfig] | None, configuration)

    @classmethod
    def _validate_io_declarations(cls) -> None:
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

    @classmethod
    def _configuration_specialization(cls) -> type[object]:
        # Find the concrete ConfigT supplied by ProcedureContract[ConfigT],
        # including specializations inherited through helper contract classes.
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
        return next(iter(specializations))

    @staticmethod
    def _validate_configuration_specialization(
        configuration: type[ProcedureConfig] | None,
        expected_configuration: type[object],
    ) -> None:
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
        if (
            not isinstance(self.contract, type)
            or not issubclass(self.contract, ProcedureContract)
            or not isinstance(
                getattr(self.contract, "metadata", None), ProcedureContractMetadata
            )
        ):
            raise TypeError(
                "procedure definition contract must be a concrete compiled "
                "ProcedureContract class"
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

    @property
    def invocation_synopsis(self) -> str:
        """Return a direct-execution synopsis without resolving implementations."""
        lines = [f"provium execute {quote(self.identifier)}"]
        lines.extend(_invocation_arguments(self.contract.metadata))
        return " \\\n  ".join(lines)

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
    "ProcedureContractMetadata",
    "ProcedureDefinition",
    "ProcedureIOFieldMetadata",
    "ProcedureInputs",
    "ProcedureOutputs",
]
