"""Built-in artifact type for generic JSON values."""

from __future__ import annotations

import json

from ...config import JsonValue, normalize_json_value
from ..definition import Artifact
from ..reader import ArtifactReader
from ..writer import ArtifactWriter


class JsonArtifactReader(ArtifactReader):
    """Read one generic JSON value from an artifact body."""

    def read(self) -> JsonValue:
        value = json.loads(self.body.read().decode("utf-8"))
        return normalize_json_value(value)


class JsonArtifactWriter(ArtifactWriter):
    """Write one generic JSON value using deterministic UTF-8 encoding."""

    def write(self, value: JsonValue) -> None:
        normalized = normalize_json_value(value)
        encoded = json.dumps(
            normalized,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        self.body.write(encoded)


class JsonArtifact(Artifact[JsonArtifactReader, JsonArtifactWriter]):
    """Artifact containing a dependency-free, generic JSON value."""

    reader = JsonArtifactReader
    writer = JsonArtifactWriter


__all__ = ["JsonArtifact", "JsonArtifactReader", "JsonArtifactWriter"]
