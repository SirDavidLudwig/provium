"""Reusable prepared procedure instances."""

from threading import Lock
from typing import Any, cast

from provium.artifact import ArtifactWriteBinding
from provium.provenance import ProcedureRecord

from .authorization import authorize_outputs
from .config import ConfigurationSnapshot, ProcedureConfig
from .context import ProcedureProcessContext, ProcedureSetupContext
from .definition import Procedure
from .execution import ProcedureExecutionSession
from .io import ProcedureInputs, ProcedureOutputs


class PreparedProcedure[
    ConfigT: ProcedureConfig | None,
    InputsT: ProcedureInputs,
    OutputsT: ProcedureOutputs,
]:
    """Own one configured procedure instance and its reusable setup state."""

    def __init__[SetupInputsT: ProcedureInputs](
        self,
        procedure: Procedure[ConfigT, SetupInputsT, InputsT, OutputsT],
        configuration: ConfigT,
        setup_inputs: SetupInputsT,
    ) -> None:
        self._procedure: Procedure[ConfigT, Any, InputsT, OutputsT] = procedure
        self._configuration = configuration
        self._state_lock = Lock()
        self._active = False
        self._closed = False
        procedure.setup(ProcedureSetupContext(), configuration, setup_inputs)

    @property
    def configuration(self) -> ConfigT:
        """Return the configuration shared by setup and every execution."""
        return self._configuration

    def execute(self, *, inputs: InputsT, outputs: OutputsT) -> None:
        """Process one invocation on the prepared instance."""
        self._begin_execution()
        try:
            output_bindings = self._output_bindings(outputs)
            if output_bindings:
                self._execute_with_outputs(inputs, outputs, output_bindings)
            else:
                with authorize_outputs({}, {}):
                    self._process(inputs, outputs)
        finally:
            self._finish_execution()

    def _execute_with_outputs(
        self,
        inputs: InputsT,
        outputs: OutputsT,
        bindings: dict[str, ArtifactWriteBinding[Any]],
    ) -> None:
        with ProcedureExecutionSession(self._procedure_record()) as execution:
            writers = execution.stage_outputs(bindings)
            with authorize_outputs(bindings, writers):
                self._process(inputs, outputs)

    def _process(self, inputs: InputsT, outputs: OutputsT) -> None:
        self._procedure.process(
            ProcedureProcessContext(),
            self._configuration,
            inputs,
            outputs,
        )

    @staticmethod
    def _output_bindings(
        outputs: ProcedureOutputs,
    ) -> dict[str, ArtifactWriteBinding[Any]]:
        values = cast(dict[str, object], object.__getattribute__(outputs, "_values"))
        return {
            name: value
            for name, value in values.items()
            if isinstance(value, ArtifactWriteBinding)
        }

    def _procedure_record(self) -> ProcedureRecord:
        definition = self._procedure.definition
        if self._configuration is None:
            return ProcedureRecord(
                definition.identifier,
                definition.contract.metadata.digest,
            )
        snapshot = ConfigurationSnapshot.from_configuration(self._configuration)
        return ProcedureRecord(
            definition.identifier,
            definition.contract.metadata.digest,
            snapshot.value,
            "pydantic-v2",
        )

    def close(self) -> None:
        """Close the prepared instance exactly once."""
        if not self._begin_close():
            return
        self._procedure.close()

    def _begin_execution(self) -> None:
        with self._state_lock:
            if self._closed:
                raise RuntimeError("prepared procedure is closed")
            if self._active:
                raise RuntimeError("prepared procedure is already executing")
            self._active = True

    def _finish_execution(self) -> None:
        with self._state_lock:
            self._active = False

    def _begin_close(self) -> bool:
        with self._state_lock:
            if self._closed:
                return False
            if self._active:
                raise RuntimeError("cannot close an executing prepared procedure")
            self._closed = True
            return True


__all__ = ["PreparedProcedure"]
