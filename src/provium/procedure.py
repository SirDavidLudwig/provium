"""Procedure definitions and configuration snapshot behavior."""

from __future__ import annotations

import hashlib
import io
from collections.abc import Callable
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from os import PathLike
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

from .artifact.catalog import ArtifactRegistration
from .artifact.definition import artifact_class_identifier
from .artifact.discovery import discover_catalogs
from .artifact.header import (
    ArtifactHeader,
    encode_header,
)
from .artifact.reader import ArtifactReader
from .artifact.region import BodyRegion
from .config import ConfigCodec, ConfigurationSnapshot, JsonValue
from .context import (
    current_context,
    current_execution_context,
    reset_context,
    reset_execution_context,
    set_context,
    set_execution_context,
)
from .provenance import (
    ArtifactLineage,
    ArtifactRecord,
    ArtifactReference,
    ProcedureExecutionRecord,
    ProcedureRecord,
)
from .session import Session, current_session

if TYPE_CHECKING:
    from .artifact.definition import Artifact
    from .artifact.writer import ArtifactWriter


_BODY_OFFSET = 4096
_direct_executions: ContextVar[dict[int, Any]] = ContextVar(
    "provium_direct_procedure_executions",
    default={},
)


@dataclass(slots=True)
class _PendingOutput:
    path: Path
    stream: io.BytesIO
    reference: ArtifactReference
    artifact_identifier: str
    writer: ArtifactWriter


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")


def _pydantic_value(config: object) -> JsonValue | None:
    """Return JSON data for a Pydantic v2 model without importing Pydantic."""
    model_dump = getattr(config, "model_dump", None)
    model_validate = getattr(type(config), "model_validate", None)
    if not callable(model_dump) or not callable(model_validate):
        return None
    return cast(JsonValue, model_dump(mode="json"))


@dataclass(frozen=True, slots=True)
class Procedure[ConfigT, StateT]:
    """Immutable procedure identity and its optional configuration codec."""

    name: str
    version: str
    config_codec: ConfigCodec[ConfigT] | None = None
    setup: Callable[[ConfigT], StateT] | None = None

    @classmethod
    def __class_getitem__(cls, parameters: Any) -> Any:
        """Default legacy one-argument annotations to no setup state."""
        if not isinstance(parameters, tuple):
            parameters = (parameters, None)
        return super(Procedure, cls).__class_getitem__(parameters)

    def __post_init__(self) -> None:
        _require_text(self.name, "name")
        _require_text(self.version, "version")
        if self.config_codec is not None:
            _require_text(self.config_codec.identifier, "config codec identifier")

    def encode_config(self, config: ConfigT | None) -> ConfigurationSnapshot | None:
        if config is None:
            return None
        if self.config_codec is not None:
            return ConfigurationSnapshot(
                self.config_codec.identifier,
                self.config_codec.encode(config),
            )
        pydantic_value = _pydantic_value(config)
        if pydantic_value is not None:
            return ConfigurationSnapshot("pydantic-v2", pydantic_value)
        raise TypeError("non-Pydantic configuration requires a config codec")

    def decode_config(self, snapshot: ConfigurationSnapshot | None) -> ConfigT | None:
        if snapshot is None:
            if self.config_codec is None:
                return None
            raise TypeError("a configuration snapshot is required")
        if self.config_codec is None:
            raise TypeError("decoding configuration requires a config codec")
        if snapshot.codec_identifier != self.config_codec.identifier:
            raise ValueError("configuration snapshot codec identifier does not match")
        return self.config_codec.decode(snapshot.value)

    def execute(
        self, *, config: ConfigT | None = None
    ) -> ExecutionContext[ConfigT, None]:
        return ExecutionContext(
            procedure=self,
            identity=str(uuid4()),
            config_snapshot=self.encode_config(config),
            state=None,
        )

    def __call__(
        self, *, config: ConfigT | None = None
    ) -> ProcedureInstance[ConfigT, StateT]:
        """Create a lazy configured instance that can execute repeatedly."""
        return ProcedureInstance(
            procedure=self,
            config=config,
            config_snapshot=self.encode_config(config),
        )

    def __enter__(self) -> ExecutionContext[ConfigT, None]:
        """Enter a fresh unconfigured execution directly from the procedure."""
        execution = self.execute()
        entered = execution.__enter__()
        active = dict(_direct_executions.get())
        active[id(self)] = execution
        _direct_executions.set(active)
        return entered

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        active = dict(_direct_executions.get())
        execution = active.pop(id(self), None)
        if execution is None:
            raise RuntimeError("procedure is not directly active")
        _direct_executions.set(active)
        execution.__exit__(exc_type, exc_value, traceback)


@dataclass(slots=True)
class _PersistentSession(Session):
    """A child session that deactivates without closing its readers."""

    owner: Session = field(default=None)  # type: ignore[assignment]
    closed: bool = False

    def __enter__(self) -> _PersistentSession:
        if self.closed:
            raise RuntimeError("persistent session is closed")
        if self.active:
            raise RuntimeError("persistent session is already active")
        if current_context() is not self.owner:
            raise RuntimeError("persistent session requires its owning session")
        self.parent = self.owner
        self.active = True
        self._token = set_context(self)
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        if not self.active or current_context() is not self or self._token is None:
            raise RuntimeError("persistent session is not active")
        token = self._token
        self.active = False
        self._token = None
        reset_context(token)

    def close(self) -> None:
        if self.closed:
            return
        if not self.active:
            self.__enter__()
        close_error: Exception | None = None
        try:
            for reader in self._readers:
                try:
                    reader.close()
                except Exception as error:  # noqa: BLE001
                    if close_error is None:
                        close_error = error
                    try:
                        reader._body.close()
                    except Exception:  # noqa: BLE001, S110
                        pass
        finally:
            self.__exit__(None, None, None)
            self.closed = True
        if close_error is not None:
            raise close_error


@dataclass(slots=True)
class ProcedureInstance[ConfigT, StateT]:
    """A lazy, session-bound procedure setup with repeatable executions."""

    procedure: Procedure[ConfigT, StateT]
    config: ConfigT | None
    config_snapshot: ConfigurationSnapshot | None
    _owner: Session | None = None
    _setup_session: _PersistentSession | None = None
    _state: StateT | None = None
    _initialized: bool = False
    _closed: bool = False
    _execution: ExecutionContext[ConfigT, StateT] | None = None

    @property
    def state(self) -> StateT:
        if self._closed:
            raise RuntimeError("procedure instance belongs to a closed session")
        if not self._initialized:
            raise RuntimeError("procedure setup has not run")
        return cast(StateT, self._state)

    def __enter__(self) -> ExecutionContext[ConfigT, StateT]:
        if self._closed:
            raise RuntimeError("procedure instance belongs to a closed session")
        if self._execution is not None:
            raise RuntimeError("procedure instance is already executing")
        if current_execution_context() is not None:
            raise RuntimeError("nested procedure execution contexts are not allowed")
        owner = current_session()
        if owner is None:
            raise RuntimeError("procedure setup requires an active session")
        if self._owner is None:
            self._owner = owner
            self._setup_session = _PersistentSession(owner=owner)
            owner._manage(self)
        elif owner is not self._owner:
            raise RuntimeError("procedure instance belongs to a different session")
        assert self._setup_session is not None
        self._setup_session.__enter__()
        try:
            if not self._initialized:
                self._state = (
                    None
                    if self.procedure.setup is None
                    else self.procedure.setup(cast(ConfigT, self.config))
                )
                self._initialized = True
            execution = ExecutionContext(
                procedure=self.procedure,
                identity=str(uuid4()),
                config_snapshot=self.config_snapshot,
                state=cast(StateT, self._state),
            )
            self._execution = execution
            return execution.__enter__()
        except Exception:
            self._setup_session.close()
            self._closed = True
            raise

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        execution = self._execution
        if execution is None or self._setup_session is None:
            raise RuntimeError("procedure instance is not executing")
        try:
            execution.__exit__(exc_type, exc_value, traceback)
        finally:
            self._execution = None
            self._setup_session.__exit__(exc_type, exc_value, traceback)

    def close(self) -> None:
        if self._closed:
            return
        if self._execution is not None:
            raise RuntimeError("cannot close an executing procedure instance")
        if self._setup_session is not None:
            self._setup_session.close()
        self._closed = True


@dataclass(slots=True)
class ExecutionContext[ConfigT, StateT]:
    """One single-use, logically scoped execution of a procedure."""

    procedure: Procedure[ConfigT, Any]
    identity: str
    config_snapshot: ConfigurationSnapshot | None
    state: StateT
    active: bool = False
    _used: bool = False
    _token: Token[object | None] | None = None
    _session: Session | None = None
    _implicit_session: Session | None = None
    _pending_outputs: list[_PendingOutput] = field(default_factory=list)

    @property
    def inputs(self) -> tuple[ArtifactRecord, ...]:
        return () if self._session is None else self._session.inputs

    @property
    def readers(self) -> tuple[ArtifactReader, ...]:
        return () if self._session is None else self._session.readers

    @property
    def input_lineage(self) -> ArtifactLineage:
        return (
            ArtifactLineage() if self._session is None else self._session.input_lineage
        )

    @property
    def input_registrations(self) -> tuple[ArtifactRegistration, ...]:
        return () if self._session is None else self._session.input_registrations

    @property
    def writers(self) -> tuple[ArtifactWriter, ...]:
        return tuple(output.writer for output in self._pending_outputs)

    @property
    def outputs(self) -> tuple[ArtifactReference, ...]:
        return tuple(output.reference for output in self._pending_outputs)

    def _owns_active_context(self) -> bool:
        return self.active and current_execution_context() is self

    def __enter__(self) -> ExecutionContext[ConfigT, StateT]:
        if self._used:
            raise RuntimeError("execution context has already been entered")
        if current_execution_context() is not None:
            raise RuntimeError("nested procedure execution contexts are not allowed")
        self._used = True
        if current_session() is None:
            self._implicit_session = Session(_discover_catalogs=discover_catalogs)
            self._implicit_session.__enter__()
        self._session = Session(_discover_catalogs=discover_catalogs)
        self._session.__enter__()
        self.active = True
        self._token = set_execution_context(self)
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        if (
            not self.active
            or current_execution_context() is not self
            or self._token is None
        ):
            raise RuntimeError("execution context is not active")
        token = self._token
        try:
            if exc_type is None:
                self._finalize_success()
            else:
                self._cleanup_failure()
        finally:
            self.active = False
            self._token = None
            reset_execution_context(token)
            try:
                assert self._session is not None
                self._session.__exit__(exc_type, exc_value, traceback)
            finally:
                if self._implicit_session is not None:
                    self._implicit_session.__exit__(exc_type, exc_value, traceback)

    def create_artifact(
        self,
        artifact: type[Artifact],
        path: str | PathLike[str],
        writer_type: type[ArtifactWriter],
    ) -> ArtifactWriter:
        from .artifact.writer import ArtifactWriter

        catalog = discover_catalogs()
        try:
            registration = catalog.registration_for(artifact)
        except KeyError:
            artifact_identifier = artifact_class_identifier(artifact)
        else:
            artifact_identifier = registration.canonical_identifier
        reference = ArtifactReference(
            str(uuid4()),
            artifact_identifier,
        )
        empty_digest = hashlib.sha256(b"").hexdigest()
        provisional_execution = ProcedureExecutionRecord(
            self.identity,
            self._procedure_record(),
            outputs=(reference,),
        )
        provisional_lineage = ArtifactLineage.for_execution(
            provisional_execution,
            (ArtifactRecord(reference, empty_digest, self.identity),),
        )
        metadata = ArtifactHeader(
            artifact_identifier=artifact_identifier,
            artifact_identity=reference.identity,
            body_offset=_BODY_OFFSET,
            body_length=0,
            body_digest=empty_digest,
            lineage=provisional_lineage,
        )
        stream = io.BytesIO(bytes(_BODY_OFFSET))
        region = BodyRegion(stream, _BODY_OFFSET, 0, self, writable=True)
        writer = writer_type(region, metadata)
        if not isinstance(writer, ArtifactWriter):
            raise TypeError("writer type must construct an ArtifactWriter")
        self._pending_outputs.append(
            _PendingOutput(Path(path), stream, reference, artifact_identifier, writer)
        )
        return writer

    def _procedure_record(self) -> ProcedureRecord:
        snapshot = self.config_snapshot
        return ProcedureRecord(
            self.procedure.name,
            self.procedure.version,
            None if snapshot is None else snapshot.value,
            None if snapshot is None else snapshot.codec_identifier,
        )

    def _finalize_success(self) -> None:
        for output in self._pending_outputs:
            output.writer.close()
        if not self._pending_outputs:
            return

        records: list[ArtifactRecord] = []
        bodies: dict[str, bytes] = {}
        for output in self._pending_outputs:
            length = output.writer._body.length
            data = output.stream.getvalue()
            body = data[_BODY_OFFSET : _BODY_OFFSET + length]
            bodies[output.reference.identity] = body
            records.append(
                ArtifactRecord(
                    output.reference,
                    hashlib.sha256(body).hexdigest(),
                    self.identity,
                )
            )
        execution = ProcedureExecutionRecord(
            self.identity,
            self._procedure_record(),
            tuple(record.reference for record in self.inputs),
            tuple(output.reference for output in self._pending_outputs),
        )
        lineage = ArtifactLineage.for_execution(
            execution,
            tuple(records),
            (self.input_lineage,) if self.inputs else (),
        )
        records_by_identity = {record.reference.identity: record for record in records}
        for output in self._pending_outputs:
            body = bodies[output.reference.identity]
            record = records_by_identity[output.reference.identity]
            header = ArtifactHeader(
                artifact_identifier=output.artifact_identifier,
                artifact_identity=output.reference.identity,
                body_offset=_BODY_OFFSET,
                body_length=len(body),
                body_digest=record.body_digest,
                lineage=lineage,
            )
            encoded = encode_header(header)
            output.path.write_bytes(encoded + bytes(_BODY_OFFSET - len(encoded)) + body)
            output.writer._replace_metadata(header)
            output.writer.finalize()

    def _cleanup_failure(self) -> None:
        resources = [output.writer for output in self._pending_outputs]
        for resource in resources:
            try:
                resource.close()
            except Exception:
                try:
                    resource._body.close()
                except Exception:
                    pass


def current_execution() -> ExecutionContext[Any, Any] | None:
    """Return the active Provium execution in this logical context."""
    context = current_execution_context()
    return context if isinstance(context, ExecutionContext) else None


__all__ = [
    "ExecutionContext",
    "Procedure",
    "ProcedureInstance",
    "current_execution",
]
