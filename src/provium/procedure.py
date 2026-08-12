"""Procedure definitions and configuration snapshot behavior."""

from __future__ import annotations

from contextvars import Token
from dataclasses import dataclass
from os import PathLike
from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

from .config import ConfigCodec, ConfigurationSnapshot, JsonValue
from .context import current_context, reset_context, set_context

if TYPE_CHECKING:
    from .artifact import Artifact
    from .reader import ArtifactReader
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
        raise NotImplementedError("artifact opening is implemented in Step 9")

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
