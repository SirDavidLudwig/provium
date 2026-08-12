"""Procedure definitions and configuration snapshot behavior."""

from __future__ import annotations

import hashlib
import io
from contextvars import Token
from dataclasses import dataclass, field
from os import PathLike
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

from .catalog import ArtifactRegistration
from .config import ConfigCodec, ConfigurationSnapshot, JsonValue
from .context import current_context, reset_context, set_context
from .discovery import discover_catalogs
from .header import decode_header
from .provenance import ArtifactLineage, ArtifactRecord, ArtifactReference
from .reader import ArtifactReader
from .region import BodyRegion

if TYPE_CHECKING:
    from .artifact import Artifact
    from .writer import ArtifactWriter


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
        data = Path(path).read_bytes()
        header = decode_header(data)
        catalog = discover_catalogs()
        try:
            registration = catalog.resolve(header.artifact_identifier)
        except KeyError as error:
            raise ValueError(
                f"unknown artifact identifier: {header.artifact_identifier}"
            ) from error
        if requested is not None and registration.artifact is not requested:
            raise TypeError("artifact does not match the requested artifact type")
        if expected is not None and registration.artifact not in expected:
            raise TypeError("artifact is outside the expected artifact types")

        body_end = header.body_offset + header.body_length
        if body_end > len(data):
            raise ValueError("artifact body is truncated")
        body = data[header.body_offset : body_end]
        if hashlib.sha256(body).hexdigest() != header.body_digest:
            raise ValueError("artifact body digest does not match")
        reference = ArtifactReference(
            header.artifact_identity,
            header.artifact_identifier,
        )
        try:
            record = header.lineage.artifact(reference)
        except (KeyError, ValueError) as error:
            raise ValueError(
                "artifact lineage does not contain the opened artifact"
            ) from error
        if record.body_digest != header.body_digest:
            raise ValueError("artifact lineage body digest does not match header")

        concrete_reader = reader_type or registration.artifact._resolve_reader()
        region = BodyRegion(
            io.BytesIO(data),
            header.body_offset,
            header.body_length,
            self,
        )
        reader = concrete_reader(region, header)
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
        raise NotImplementedError("artifact creating is implemented in Step 10")


def current_execution() -> ExecutionContext[Any] | None:
    """Return the active Provium execution in this logical context."""
    context = current_context()
    return context if isinstance(context, ExecutionContext) else None


__all__ = ["ExecutionContext", "Procedure", "current_execution"]
