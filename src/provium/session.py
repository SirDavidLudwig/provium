"""Nested artifact-reading sessions and their append-only dependency ledgers."""

from __future__ import annotations

import hashlib
import io
import struct
from collections.abc import Callable
from contextvars import Token
from dataclasses import dataclass, field
from os import PathLike
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .artifact.catalog import ArtifactRegistration
from .artifact.definition import artifact_class_identifier
from .artifact.discovery import discover_catalogs
from .artifact.header import (
    CONTAINER_VERSION,
    MAGIC,
    PREFIX_SIZE,
    ArtifactHeader,
    decode_header,
)
from .artifact.reader import ArtifactReader
from .artifact.region import BodyRegion
from .context import current_context, reset_context, set_context
from .provenance import ArtifactLineage, ArtifactRecord

if TYPE_CHECKING:
    from .artifact.definition import Artifact


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


@dataclass(slots=True)
class Session:
    """A nested scope for artifact resources and observed dependencies."""

    active: bool = False
    parent: Session | None = None
    _used: bool = False
    _token: Token[object | None] | None = None
    _inputs: dict[str, ArtifactRecord] = field(default_factory=dict)
    _readers: list[ArtifactReader] = field(default_factory=list)
    _input_lineage: ArtifactLineage = field(default_factory=ArtifactLineage)
    _input_registrations: list[ArtifactRegistration] = field(default_factory=list)
    _discover_catalogs: Callable[[], Any] | None = None

    def __enter__(self) -> Session:
        if self._used:
            raise RuntimeError("session has already been entered")
        parent = current_context()
        if parent is not None and not isinstance(parent, Session):
            raise RuntimeError("active artifact context is not a session")
        self._used = True
        self.parent = parent
        self.active = True
        self._token = set_context(self)
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        if not self.active or current_context() is not self or self._token is None:
            raise RuntimeError("session is not active")
        token = self._token
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
            self.active = False
            self._token = None
            reset_context(token)
        if exc_type is None and close_error is not None:
            raise close_error

    def _owns_active_context(self) -> bool:
        current = current_context()
        while isinstance(current, Session):
            if current is self:
                return self.active
            current = current.parent
        return False

    @property
    def inputs(self) -> tuple[ArtifactRecord, ...]:
        combined = (
            {}
            if self.parent is None
            else {record.reference.identity: record for record in self.parent.inputs}
        )
        combined.update(self._inputs)
        return tuple(combined.values())

    @property
    def readers(self) -> tuple[ArtifactReader, ...]:
        return tuple(self._readers)

    @property
    def input_lineage(self) -> ArtifactLineage:
        if self.parent is None:
            return self._input_lineage
        return self.parent.input_lineage.merge(self._input_lineage)

    @property
    def input_registrations(self) -> tuple[ArtifactRegistration, ...]:
        inherited = () if self.parent is None else self.parent.input_registrations
        return (*inherited, *self._input_registrations)

    def open_artifact(
        self,
        artifact: type[Artifact],
        path: str | PathLike[str],
        reader_type: type[ArtifactReader],
    ) -> ArtifactReader:
        return self._open(path, requested=artifact, reader_type=reader_type)

    def open_unknown_artifact(
        self, path: str | PathLike[str], expected: tuple[type[Artifact], ...] | None
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
            catalog = (self._discover_catalogs or discover_catalogs)()
            try:
                registration = catalog.resolve(header.artifact_identifier)
            except KeyError:
                registration = None
            if requested is not None:
                matches = (
                    registration is not None and registration.artifact is requested
                ) or (
                    registration is None
                    and header.artifact_identifier
                    == artifact_class_identifier(requested)
                )
                if not matches:
                    raise TypeError(  # noqa: TRY301
                        "artifact does not match the requested artifact type"
                    )
            elif registration is None:
                raise ValueError(  # noqa: TRY301
                    f"unknown artifact identifier: {header.artifact_identifier}"
                )
            if expected is not None and registration.artifact not in expected:
                raise TypeError(  # noqa: TRY301
                    "artifact is outside the expected artifact types"
                )
            metadata_end = header.metadata_offset + header.metadata_length
            if header.body_offset < metadata_end:
                raise ValueError(  # noqa: TRY301
                    "artifact body offset overlaps its header metadata"
                )
            if header.body_offset + header.body_length > file_length:
                raise ValueError("artifact body is truncated")  # noqa: TRY301
            digest = hashlib.sha256()
            stream.seek(header.body_offset)
            for offset in range(0, header.body_length, 1024 * 1024):
                digest.update(
                    stream.read(min(1024 * 1024, header.body_length - offset))
                )
            if digest.hexdigest() != header.body_digest:
                raise ValueError(  # noqa: TRY301
                    "artifact body digest does not match"
                )
            from .provenance import ArtifactReference

            reference = ArtifactReference(
                header.artifact_identity, header.artifact_identifier
            )
            try:
                record = header.lineage.artifact(reference)
            except (KeyError, ValueError) as error:
                raise ValueError(
                    "artifact lineage does not contain the opened artifact"
                ) from error
            if record.body_digest != header.body_digest:
                raise ValueError(  # noqa: TRY301
                    "artifact lineage body digest does not match header"
                )
            concrete_reader = reader_type or registration.artifact._resolve_reader()
            region = BodyRegion(
                stream, header.body_offset, header.body_length, self, close_stream=True
            )
            reader = concrete_reader(region, header)
        except Exception:
            stream.close()
            raise
        self._readers.append(reader)
        self._inputs.setdefault(record.reference.identity, record)
        self._input_lineage = self._input_lineage.merge(header.lineage)
        if registration is not None:
            self._input_registrations.append(registration)
        return reader


def session() -> Session:
    """Create a generic nested artifact session."""
    return Session()


def current_session() -> Session | None:
    current = current_context()
    return current if isinstance(current, Session) else None


__all__ = ["Session", "current_session", "session"]
