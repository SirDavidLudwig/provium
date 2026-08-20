"""Procedure preparation and execution orchestration."""

from collections.abc import Iterable, Mapping
from inspect import signature
from typing import Any, cast

from provium.artifact import ArtifactReadBinding

from .config import ProcedureConfig, compose_configuration
from .definition import Procedure, ProcedureDefinition
from .io import ProcedureInputs, build_procedure_inputs
from .prepared import PreparedProcedure
from .validation import validate_procedure_configuration


class ProcedureExecutor:
    """Resolve, validate, and prepare procedure implementations."""

    def prepare[ProcedureT: Procedure[Any, Any, Any, Any]](
        self,
        definition: ProcedureDefinition[ProcedureT],
        *,
        configuration_layers: Iterable[Mapping[str, object]] = (),
        setup_inputs: Mapping[str, ArtifactReadBinding[Any]] | None = None,
    ) -> PreparedProcedure[Any, Any, Any]:
        """Create and set up one reusable procedure instance."""
        procedure_type = definition.resolve()
        configuration = self._prepare_configuration(
            definition,
            configuration_layers,
        )
        inputs = self._prepare_setup_inputs(definition, setup_inputs)
        procedure = self._instantiate(definition, procedure_type)
        return PreparedProcedure(procedure, configuration, inputs)

    @staticmethod
    def _instantiate(
        definition: ProcedureDefinition[Any],
        procedure_type: type[Procedure[Any, Any, Any, Any]],
    ) -> Procedure[Any, Any, Any, Any]:
        try:
            signature(procedure_type).bind()
        except TypeError as error:
            raise TypeError(
                f"procedure {definition.identifier} must be constructible without "
                "arguments"
            ) from error
        return procedure_type()

    @staticmethod
    def _prepare_configuration(
        definition: ProcedureDefinition[Any],
        layers: Iterable[Mapping[str, object]],
    ) -> ProcedureConfig | None:
        values = compose_configuration(layers)
        configuration_type = cast(
            type[ProcedureConfig] | None,
            getattr(definition.contract, "configuration"),
        )
        if configuration_type is None:
            if values:
                raise TypeError(
                    f"procedure {definition.identifier} does not accept configuration"
                )
            return None
        return validate_procedure_configuration(
            definition.identifier,
            configuration_type,
            values,
        )

    @staticmethod
    def _prepare_setup_inputs(
        definition: ProcedureDefinition[Any],
        supplied: Mapping[str, ArtifactReadBinding[Any]] | None,
    ) -> ProcedureInputs:
        bindings: Mapping[str, object] = {} if supplied is None else supplied
        record_type = cast(
            type[ProcedureInputs],
            getattr(definition.contract, "SetupInputs"),
        )
        return build_procedure_inputs(record_type, bindings)


__all__ = ["ProcedureExecutor"]
