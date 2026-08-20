"""Procedure configuration models."""

import json
from collections.abc import Iterable, Mapping
from copy import deepcopy
from os import PathLike
from pathlib import Path
from typing import Never, cast

from pydantic import BaseModel, ConfigDict


class ProcedureConfig(BaseModel):
    """Immutable, strictly validated configuration for a procedure."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_default=True,
    )


def compose_configuration(
    layers: Iterable[Mapping[str, object]],
) -> dict[str, object]:
    """Merge ordered raw configuration layers without mutating their values."""
    composed: dict[str, object] = {}
    for layer in layers:
        composed = _merge_mappings(composed, layer)
    return composed


def load_json_configuration(path: str | PathLike[str]) -> dict[str, object]:
    """Load one raw configuration layer from a UTF-8 JSON object."""
    configuration_path = Path(path)
    document = configuration_path.read_text(encoding="utf-8")

    def reject_non_finite(constant: str) -> Never:
        raise json.JSONDecodeError(
            f"non-finite number {constant} is not valid JSON", document, 0
        )

    value = cast(
        object,
        json.loads(document, parse_constant=reject_non_finite),
    )
    if not isinstance(value, dict):
        raise TypeError(f"configuration root must be an object: {configuration_path}")
    return cast(dict[str, object], value)


def _merge_mappings(
    earlier: Mapping[str, object],
    later: Mapping[str, object],
) -> dict[str, object]:
    merged = _copy_mapping(earlier)
    for key, later_value in later.items():
        earlier_value = merged.get(key)
        if isinstance(earlier_value, Mapping) and isinstance(later_value, Mapping):
            merged[key] = _merge_mappings(
                cast(Mapping[str, object], earlier_value),
                cast(Mapping[str, object], later_value),
            )
        else:
            merged[key] = _copy_value(later_value)
    return merged


def _copy_mapping(value: Mapping[str, object]) -> dict[str, object]:
    return {key: _copy_value(item) for key, item in value.items()}


def _copy_value(value: object) -> object:
    if isinstance(value, Mapping):
        return _copy_mapping(cast(Mapping[str, object], value))
    return deepcopy(value)


__all__ = [
    "ProcedureConfig",
    "compose_configuration",
    "load_json_configuration",
]
