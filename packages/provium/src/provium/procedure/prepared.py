"""Reusable prepared procedure instances."""

from threading import Lock
from typing import Any, Never, cast
from uuid import uuid4

from provium.artifact import ArtifactReadBinding, ArtifactWriteBinding
from provium.provenance import ProcedureRecord
from provium.session import PersistentSession, Session, session

from .authorization import authorize_bindings
from .config import ConfigurationSnapshot, ProcedureConfig
from .context import ProcedureProcessContext, ProcedureSetupContext
from .definition import Procedure, ProcedureDefinition
from .execution import ProcedureExecutionSession
from .io import ProcedureInputs, ProcedureOutputs
from .result import ProcedureExecutionResult


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
        self._setup_session = PersistentSession()
        self._setup_bindings = self._input_bindings(setup_inputs)
        self._setup_identities: dict[int, str] = {}
        try:
            self._run_setup(setup_inputs)
        except BaseException as error:
            self._close_setup_after_failure(error)

    def _run_setup(self, setup_inputs: ProcedureInputs) -> None:
        with self._setup_session:
            with authorize_bindings(self._setup_bindings, {}, {}):
                self._setup_identities = self._register_inputs(self._setup_bindings)
            with authorize_bindings(
                self._setup_bindings,
                {},
                {},
                input_identities=self._setup_identities,
            ):
                self._procedure.setup(
                    ProcedureSetupContext(),
                    self._configuration,
                    setup_inputs,
                )

    @property
    def configuration(self) -> ConfigT:
        """Return the configuration shared by setup and every execution."""
        return self._configuration

    def execute(
        self, *, inputs: InputsT, outputs: OutputsT
    ) -> ProcedureExecutionResult:
        """Process one invocation on the prepared instance."""
        self._begin_execution()
        try:
            with self._setup_session:
                return self._execute_active(inputs, outputs)
        finally:
            self._finish_execution()

    def _execute_active(
        self,
        inputs: InputsT,
        outputs: OutputsT,
    ) -> ProcedureExecutionResult:
        input_bindings = self._input_bindings(inputs)
        output_bindings = self._output_bindings(outputs)
        if output_bindings:
            return self._execute_with_outputs(
                inputs,
                outputs,
                input_bindings,
                output_bindings,
            )
        if input_bindings:
            return self._execute_without_outputs(inputs, outputs, input_bindings)
        with authorize_bindings((), {}, {}):
            self._process(inputs, outputs)
        return self._execution_result(self._setup_session)

    def _execute_with_outputs(
        self,
        inputs: InputsT,
        outputs: OutputsT,
        input_bindings: tuple[ArtifactReadBinding[Any], ...],
        output_bindings: dict[str, ArtifactWriteBinding[Any]],
    ) -> ProcedureExecutionResult:
        with ProcedureExecutionSession(self._procedure_record()) as execution:
            with authorize_bindings(input_bindings, {}, {}):
                identities = self._register_inputs(input_bindings)
            writers = execution.stage_outputs(output_bindings)
            with authorize_bindings(
                input_bindings,
                output_bindings,
                writers,
                input_identities=identities,
            ):
                self._process(inputs, outputs)
        return cast(ProcedureExecutionResult, execution.result)

    def _execute_without_outputs(
        self,
        inputs: InputsT,
        outputs: OutputsT,
        input_bindings: tuple[ArtifactReadBinding[Any], ...],
    ) -> ProcedureExecutionResult:
        with session() as active:
            with authorize_bindings(input_bindings, {}, {}):
                identities = self._register_inputs(input_bindings)
            with authorize_bindings(
                input_bindings,
                {},
                {},
                input_identities=identities,
            ):
                self._process(inputs, outputs)
            return self._execution_result(active)

    def _process(self, inputs: InputsT, outputs: OutputsT) -> None:
        self._procedure.process(
            ProcedureProcessContext(),
            self._configuration,
            inputs,
            outputs,
        )

    @staticmethod
    def _input_bindings(
        inputs: ProcedureInputs,
    ) -> tuple[ArtifactReadBinding[Any], ...]:
        values = cast(dict[str, object], object.__getattribute__(inputs, "_values"))
        bindings: list[ArtifactReadBinding[Any]] = []
        for value in values.values():
            if isinstance(value, tuple):
                bindings.extend(cast(tuple[ArtifactReadBinding[Any], ...], value))
            elif value is not None:
                bindings.append(cast(ArtifactReadBinding[Any], value))
        return tuple(bindings)

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

    @staticmethod
    def _register_inputs(
        bindings: tuple[ArtifactReadBinding[Any], ...],
    ) -> dict[int, str]:
        identities: dict[int, str] = {}
        for binding in bindings:
            reader = binding.open()
            identities[id(binding)] = reader.identity
            reader.close()
        return identities

    def _procedure_record(self) -> ProcedureRecord:
        record = self._optional_procedure_record()
        if record is None:
            raise TypeError("artifact-producing procedure must declare a definition")
        return record

    def _optional_procedure_record(self) -> ProcedureRecord | None:
        definition = getattr(self._procedure, "definition", None)
        if not isinstance(definition, ProcedureDefinition):
            return None
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

    def _execution_result(self, active: Session) -> ProcedureExecutionResult:
        return ProcedureExecutionResult(
            str(uuid4()),
            self._optional_procedure_record(),
            tuple(record.reference for record in active.inputs),
            lineage=active.input_lineage,
        )

    def close(self) -> None:
        """Close the prepared instance exactly once."""
        if not self._begin_close():
            return
        close_error = self._close_procedure()
        self._close_setup_resources(close_error)

    def _close_procedure(self) -> BaseException | None:
        close_error: BaseException | None = None
        try:
            with self._setup_session:
                with authorize_bindings(
                    self._setup_bindings,
                    {},
                    {},
                    input_identities=self._setup_identities,
                ):
                    self._procedure.close()
        except BaseException as error:
            close_error = error
        return close_error

    def _close_setup_resources(self, close_error: BaseException | None) -> None:
        try:
            self._setup_session.close()
        except BaseException as setup_close_error:
            if close_error is not None:
                raise close_error from setup_close_error
            raise
        if close_error is not None:
            raise close_error

    def _close_setup_after_failure(self, error: BaseException) -> Never:
        try:
            self._setup_session.close()
        except BaseException as close_error:
            raise error from close_error
        raise error

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
