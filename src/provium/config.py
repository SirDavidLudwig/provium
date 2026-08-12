"""Typed, dependency-free procedure configuration serialization."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Protocol

type JsonScalar = None | bool | int | float | str
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]


class ConfigCodec[ConfigT](Protocol):
    """Encode and decode one procedure configuration type."""

    identifier: str

    def encode(self, config: ConfigT) -> JsonValue: ...

    def decode(self, value: JsonValue) -> ConfigT: ...


def _canonical_json_value(value: object) -> JsonValue:
    """Validate a JSON value and return an independent normalized copy."""
    _validate_json_value(value)
    encoded = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    decoded: JsonValue = json.loads(encoded)
    return decoded


def _validate_json_value(value: object) -> None:
    if value is None or isinstance(value, (bool, int, str)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("configuration must contain finite JSON numbers")
        return
    if isinstance(value, list):
        for item in value:
            _validate_json_value(item)
        return
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("configuration JSON object keys must be strings")
        for item in value.values():
            _validate_json_value(item)
        return
    raise TypeError("configuration must be a JSON value")


@dataclass(frozen=True, slots=True)
class ConfigurationSnapshot:
    """A JSON-compatible configuration value paired with its codec identity."""

    codec_identifier: str
    value: JsonValue

    def __post_init__(self) -> None:
        if not isinstance(self.codec_identifier, str) or not self.codec_identifier:
            raise ValueError("codec_identifier must be a non-empty string")
        object.__setattr__(self, "value", _canonical_json_value(self.value))

    def to_json(self) -> str:
        return json.dumps(
            {"codec_identifier": self.codec_identifier, "value": self.value},
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    @classmethod
    def from_json(cls, value: str) -> ConfigurationSnapshot:
        decoded = json.loads(value)
        if not isinstance(decoded, dict) or set(decoded) != {
            "codec_identifier",
            "value",
        }:
            raise ValueError("invalid configuration snapshot")
        return cls(decoded["codec_identifier"], decoded["value"])


__all__ = ["ConfigCodec", "ConfigurationSnapshot", "JsonValue"]
