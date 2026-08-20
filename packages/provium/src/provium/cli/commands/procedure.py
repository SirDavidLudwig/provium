"""Procedure inspection and direct execution commands."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from provium import (
    ArtifactReadBinding,
    ArtifactWriteBinding,
    ProcedureDefinition,
    ProcedureExecutor,
    ProcedureIOFieldMetadata,
    discover_procedure_catalogs,
    load_json_configuration,
    load_yaml_configuration,
)

from ..command import Command


def _definition(identifier: str) -> ProcedureDefinition[Any]:
    try:
        return discover_procedure_catalogs().resolve(identifier)
    except KeyError:
        raise ValueError(f"unknown procedure: {identifier}") from None


def _print_error(error: BaseException) -> int:
    print(f"error: {error}", file=sys.stderr)
    return 2


class ProcedureCommand(Command):
    """List and inspect discovered procedure definitions."""

    name = "procedure"
    help = "List and inspect procedures"

    def configure(self, parser: argparse.ArgumentParser) -> None:
        actions = parser.add_subparsers(dest="procedure_action", required=True)
        list_parser = actions.add_parser("list", help="List procedures")
        list_parser.set_defaults(procedure_handler=self._list)
        show_parser = actions.add_parser("show", help="Show a procedure")
        show_parser.add_argument("identifier")
        show_parser.add_argument(
            "--resolve",
            action="store_true",
            help="Import and validate the implementation",
        )
        show_parser.set_defaults(procedure_handler=self._show)

    def execute(self, arguments: argparse.Namespace) -> int:
        try:
            return arguments.procedure_handler(arguments)
        except (ImportError, OSError, RuntimeError, TypeError, ValueError) as error:
            return _print_error(error)

    @staticmethod
    def _list(arguments: argparse.Namespace) -> int:
        del arguments
        definitions = discover_procedure_catalogs().definitions
        for identifier in sorted(definitions):
            definition = definitions[identifier]
            print(f"{identifier}\t{definition.label}")
        return 0

    @staticmethod
    def _show(arguments: argparse.Namespace) -> int:
        definition = _definition(arguments.identifier)
        contract = definition.resolve_contract()
        print(f"{definition.label} ({definition.identifier})")
        if definition.description is not None:
            print(definition.description)
        print("\nInvocation:")
        print(definition.invocation_synopsis)
        ProcedureCommand._print_fields("Setup inputs", contract.metadata.setup_inputs)
        ProcedureCommand._print_fields("Inputs", contract.metadata.inputs)
        ProcedureCommand._print_fields("Outputs", contract.metadata.outputs)
        schema = contract.metadata.configuration_schema
        if schema is not None:
            print("\nConfiguration:")
            print(json.dumps(schema, indent=2, sort_keys=True))
        if arguments.resolve:
            implementation = definition.resolve()
            target = f"{implementation.__module__}.{implementation.__qualname__}"
            print(f"\nResolved: {target}")
        return 0

    @staticmethod
    def _print_fields(
        heading: str,
        fields: tuple[ProcedureIOFieldMetadata, ...],
    ) -> None:
        if not fields:
            return
        print(f"\n{heading}:")
        for field in fields:
            maximum = "many" if field.maximum is None else str(field.maximum)
            print(
                f"  {field.name}: {field.artifact_identifier} "
                f"[{field.minimum}..{maximum}]"
            )


class ExecuteCommand(Command):
    """Execute one discovered procedure directly."""

    name = "execute"
    help = "Execute a procedure"

    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("identifier")
        parser.add_argument("--config", action="append", default=[])
        parser.add_argument("--setup-input", action="append", default=[])
        parser.add_argument("--input", action="append", default=[])
        parser.add_argument("--output", action="append", default=[])

    def execute(self, arguments: argparse.Namespace) -> int:
        try:
            definition = _definition(arguments.identifier)
            contract = definition.resolve_contract()
            layers = tuple(self._load_configuration(path) for path in arguments.config)
            setup_inputs = self._read_bindings(
                contract.SetupInputs.fields,
                arguments.setup_input,
            )
            inputs = self._read_bindings(
                contract.Inputs.fields,
                arguments.input,
            )
            outputs = self._write_bindings(
                contract.Outputs.fields,
                arguments.output,
            )
            result = ProcedureExecutor().execute(
                definition,
                configuration_layers=layers,
                setup_inputs=setup_inputs,
                inputs=inputs,
                outputs=outputs,
            )
        except (ImportError, OSError, RuntimeError, TypeError, ValueError) as error:
            return _print_error(error)
        print(result.identity)
        return 0

    @staticmethod
    def _load_configuration(path_value: str) -> Mapping[str, object]:
        path = Path(path_value)
        if path.suffix.casefold() == ".json":
            return load_json_configuration(path)
        if path.suffix.casefold() in {".yaml", ".yml"}:
            return load_yaml_configuration(path)
        raise ValueError(f"unsupported configuration file type: {path}")

    @staticmethod
    def _assignments(values: Sequence[str]) -> dict[str, list[Path]]:
        assignments: dict[str, list[Path]] = {}
        for value in values:
            name, separator, path = value.partition("=")
            if not separator or not name or not path:
                raise ValueError(f"binding must use FIELD=PATH syntax: {value}")
            assignments.setdefault(name, []).append(Path(path))
        return assignments

    @classmethod
    def _read_bindings(
        cls,
        fields: Mapping[str, Any],
        values: Sequence[str],
    ) -> dict[str, ArtifactReadBinding[Any] | list[ArtifactReadBinding[Any]]]:
        result: dict[
            str, ArtifactReadBinding[Any] | list[ArtifactReadBinding[Any]]
        ] = {}
        for name, paths in cls._assignments(values).items():
            field = cls._field(fields, name)
            artifact = field.artifact.resolve()
            bindings = [artifact.bind_read(path) for path in paths]
            result[name] = bindings if field.repeated else cls._single(name, bindings)
        return result

    @classmethod
    def _write_bindings(
        cls,
        fields: Mapping[str, Any],
        values: Sequence[str],
    ) -> dict[str, ArtifactWriteBinding[Any]]:
        result: dict[str, ArtifactWriteBinding[Any]] = {}
        for name, paths in cls._assignments(values).items():
            field = cls._field(fields, name)
            artifact = field.artifact.resolve()
            result[name] = artifact.bind_write(cls._single(name, paths))
        return result

    @staticmethod
    def _field(fields: Mapping[str, Any], name: str) -> Any:
        try:
            return fields[name]
        except KeyError:
            raise ValueError(f"unknown binding field: {name}") from None

    @staticmethod
    def _single[T](name: str, values: Sequence[T]) -> T:
        if len(values) != 1:
            raise ValueError(f"binding field {name} may be supplied only once")
        return values[0]


__all__ = ["ExecuteCommand", "ProcedureCommand"]
