"""Word frequency artifact implementation."""

import json
from collections.abc import Mapping

from provium import Artifact, ArtifactReader, ArtifactWriter


class WordStatsReader(ArtifactReader):
    """Read a token->count mapping."""

    def read(self) -> dict[str, int]:
        payload = self.body.read().decode("utf-8")
        values = json.loads(payload)
        if not isinstance(values, Mapping):
            raise TypeError("word stats artifact payload must be a JSON object")
        raw = dict(values)
        return {
            _require_text(key, "word stats key"): _require_int(
                value, "word stats value"
            )
            for key, value in raw.items()
        }


class WordStatsWriter(ArtifactWriter):
    """Write a token->count mapping."""

    def write(self, value: Mapping[str, int]) -> int:
        payload = json.dumps(
            {str(key): int(count) for key, count in value.items()},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return self.body.write(payload.encode("utf-8"))


class WordStatsArtifact(Artifact[WordStatsReader, WordStatsWriter]):
    reader = WordStatsReader
    writer = WordStatsWriter


def _require_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value:
        raise ValueError(f"{field_name} must not be empty")
    return value


def _require_int(value: object, field_name: str) -> int:
    if not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    return value


__all__ = [
    "WordStatsArtifact",
    "WordStatsReader",
    "WordStatsWriter",
]
