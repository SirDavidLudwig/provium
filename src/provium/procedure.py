"""Procedure definitions and configuration snapshot behavior."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from .config import ConfigCodec, ConfigurationSnapshot, JsonValue


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


__all__ = ["Procedure"]
