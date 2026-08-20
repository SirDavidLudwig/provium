"""Reusable prepared procedure instances."""

from threading import Lock
from typing import Any

from .config import ProcedureConfig
from .context import ProcedureProcessContext, ProcedureSetupContext
from .definition import Procedure
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
            self._procedure.process(
                ProcedureProcessContext(),
                self._configuration,
                inputs,
                outputs,
            )
        finally:
            self._finish_execution()

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
