"""Procedure definitions and configuration snapshot behavior."""

from __future__ import annotations

import hashlib
import io
import struct
from contextvars import Token
from dataclasses import dataclass, field
from os import PathLike
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

from .artifact.catalog import ArtifactRegistration
from .artifact.discovery import discover_catalogs
from .artifact.header import (
    CONTAINER_VERSION,
    MAGIC,
    PREFIX_SIZE,
    ArtifactHeader,
    decode_header,
    encode_header,
)
from .artifact.reader import ArtifactReader
from .artifact.region import BodyRegion
from .config import ConfigCodec, ConfigurationSnapshot, JsonValue
from .context import current_context, reset_context, set_context
from .provenance import (
    ArtifactLineage,
    ArtifactRecord,
    ArtifactReference,
    ProcedureExecutionRecord,
    ProcedureRecord,
)

if TYPE_CHECKING:
    from .artifact.definition import Artifact
    from .artifact.writer import ArtifactWriter


_BODY_OFFSET = 4096


@dataclass(slots=True)
class _PendingOutput:
    path: Path
    stream: io.BytesIO
    reference: ArtifactReference
    registration: ArtifactRegistration
    writer: ArtifactWriter


def _read_header_from_stream(stream: Any) -> tuple[ArtifactHeader, int]:
    prefix = stream.read(PREFIX_SIZE)
    if len(prefix) < PREFIX_SIZE:
        raise ValueError("truncated fixed header")
    magic, version, metadata_offset, metadata_length = struct.unpack(">8sHQQ", prefix)
    if magic != MAGIC:
        raise ValueError("invalid artifact magic bytes")
    if version != CONTAINER_VERSION:
        raise ValueError(f"unsupported container version: {version}")
    metadata_end = metadata_offset + metadata_length
    stream.seek(0)
    header = decode_header(stream.read(metadata_end))
    stream.seek(0, io.SEEK_END)
    return header, stream.tell()


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
class Procedure[ConfigT]:
    """Immutable procedure identity and its optional configuration codec."""

    name: str
    version: str
    config_codec: ConfigCodec[ConfigT] | None = None

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

    def execute(self, *, config: ConfigT | None = None) -> ExecutionContext[ConfigT]:
        return ExecutionContext(
            procedure=self,
            identity=str(uuid4()),
            config_snapshot=self.encode_config(config),
        )


@dataclass(slots=True)
class ExecutionContext[ConfigT]:
    """One single-use, logically scoped execution of a procedure."""

    procedure: Procedure[ConfigT]
    identity: str
    config_snapshot: ConfigurationSnapshot | None
    active: bool = False
    _used: bool = False
    _token: Token[object | None] | None = None
    _inputs: dict[str, ArtifactRecord] = field(default_factory=dict)
    _readers: list[ArtifactReader] = field(default_factory=list)
    _input_lineage: ArtifactLineage = field(default_factory=ArtifactLineage)
    _input_registrations: list[ArtifactRegistration] = field(default_factory=list)
    _pending_outputs: list[_PendingOutput] = field(default_factory=list)

    @property
    def inputs(self) -> tuple[ArtifactRecord, ...]:
        return tuple(self._inputs.values())

    @property
    def readers(self) -> tuple[ArtifactReader, ...]:
        return tuple(self._readers)

    @property
    def input_lineage(self) -> ArtifactLineage:
        return self._input_lineage

    @property
    def input_registrations(self) -> tuple[ArtifactRegistration, ...]:
        return tuple(self._input_registrations)

    @property
    def writers(self) -> tuple[ArtifactWriter, ...]:
        return tuple(output.writer for output in self._pending_outputs)

    @property
    def outputs(self) -> tuple[ArtifactReference, ...]:
        return tuple(output.reference for output in self._pending_outputs)

    def __enter__(self) -> ExecutionContext[ConfigT]:
        if self._used:
            raise RuntimeError("execution context has already been entered")
        if current_context() is not None:
            raise RuntimeError("nested procedure execution contexts are not allowed")
        self._used = True
        self.active = True
        self._token = set_context(self)
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        if not self.active or current_context() is not self or self._token is None:
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
            reset_context(token)

    def open_artifact(
        self,
        artifact: type[Artifact],
        path: str | PathLike[str],
        reader_type: type[ArtifactReader],
    ) -> ArtifactReader:
        return self._open(path, requested=artifact, reader_type=reader_type)

    def open_unknown_artifact(
        self,
        path: str | PathLike[str],
        expected: tuple[type[Artifact], ...] | None,
    ) -> ArtifactReader:
        return self._open(path, expected=expected)

    def _open(
        self,
        path: str | PathLike[str],
        *,
        requested: type[Artifact] | None = None,
        reader_type: type[ArtifactReader] | None = None,
        expected: tuple[type[Artifact], ...] | None = None,
    ) -> ArtifactReader:
        stream = Path(path).open("rb")
        try:
            header, file_length = _read_header_from_stream(stream)
        except Exception:
            stream.close()
            raise
        catalog = discover_catalogs()
        try:
            registration = catalog.resolve(header.artifact_identifier)
        except KeyError as error:
            stream.close()
            raise ValueError(
                f"unknown artifact identifier: {header.artifact_identifier}"
            ) from error
        if requested is not None and registration.artifact is not requested:
            stream.close()
            raise TypeError("artifact does not match the requested artifact type")
        if expected is not None and registration.artifact not in expected:
            stream.close()
            raise TypeError("artifact is outside the expected artifact types")

        metadata_end = header.metadata_offset + header.metadata_length
        if header.body_offset < metadata_end:
            stream.close()
            raise ValueError("artifact body offset overlaps its header metadata")
        body_end = header.body_offset + header.body_length
        if body_end > file_length:
            stream.close()
            raise ValueError("artifact body is truncated")
        digest = hashlib.sha256()
        stream.seek(header.body_offset)
        chunk_size = 1024 * 1024
        for offset in range(0, header.body_length, chunk_size):
            digest.update(stream.read(min(chunk_size, header.body_length - offset)))
        if digest.hexdigest() != header.body_digest:
            stream.close()
            raise ValueError("artifact body digest does not match")
        reference = ArtifactReference(
            header.artifact_identity,
            header.artifact_identifier,
        )
        try:
            record = header.lineage.artifact(reference)
        except (KeyError, ValueError) as error:
            stream.close()
            raise ValueError(
                "artifact lineage does not contain the opened artifact"
            ) from error
        if record.body_digest != header.body_digest:
            stream.close()
            raise ValueError("artifact lineage body digest does not match header")

        concrete_reader = reader_type or registration.artifact._resolve_reader()
        region = BodyRegion(
            stream,
            header.body_offset,
            header.body_length,
            self,
            close_stream=True,
        )
        try:
            reader = concrete_reader(region, header)
        except Exception:
            stream.close()
            raise
        self._readers.append(reader)
        self._inputs.setdefault(record.reference.identity, record)
        self._input_lineage = self._input_lineage.merge(header.lineage)
        self._input_registrations.append(registration)
        return reader

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
        except KeyError as error:
            raise ValueError("artifact class is not registered") from error
        reference = ArtifactReference(
            str(uuid4()),
            registration.canonical_identifier,
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
            artifact_identifier=registration.canonical_identifier,
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
            _PendingOutput(Path(path), stream, reference, registration, writer)
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
        for reader in self._readers:
            reader.close()
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
            tuple(record.reference for record in self._inputs.values()),
            tuple(output.reference for output in self._pending_outputs),
        )
        lineage = ArtifactLineage.for_execution(
            execution,
            tuple(records),
            (self._input_lineage,) if self._inputs else (),
        )
        records_by_identity = {record.reference.identity: record for record in records}
        for output in self._pending_outputs:
            body = bodies[output.reference.identity]
            record = records_by_identity[output.reference.identity]
            header = ArtifactHeader(
                artifact_identifier=output.registration.canonical_identifier,
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
        resources = [
            *self._readers,
            *(output.writer for output in self._pending_outputs),
        ]
        for resource in resources:
            try:
                resource.close()
            except Exception:
                try:
                    resource._body.close()
                except Exception:
                    pass


def current_execution() -> ExecutionContext[Any] | None:
    """Return the active Provium execution in this logical context."""
    context = current_context()
    return context if isinstance(context, ExecutionContext) else None


__all__ = ["ExecutionContext", "Procedure", "current_execution"]
