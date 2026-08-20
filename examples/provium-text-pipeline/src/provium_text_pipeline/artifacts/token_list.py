"""Token list artifact implementation."""

import json
from collections.abc import Sequence

from provium import Artifact, ArtifactReader, ArtifactWriter


class TokenListReader(ArtifactReader):
    """Read an ordered tuple of string tokens."""

    def read(self) -> tuple[str, ...]:
        payload = self.body.read().decode("utf-8")
        values = json.loads(payload)
        if not isinstance(values, list):
            raise TypeError("token list artifact payload must be a JSON list")
        return tuple(_require_text(item, "token") for item in values)


class TokenListWriter(ArtifactWriter):
    """Write an ordered tuple or list of string tokens."""

    def write(self, value: Sequence[str] | tuple[str, ...]) -> int:
        payload = json.dumps(list(value), separators=(",", ":"), ensure_ascii=False)
        return self.body.write(payload.encode("utf-8"))


class TokenListArtifact(Artifact[TokenListReader, TokenListWriter]):
    reader = TokenListReader
    writer = TokenListWriter


def _require_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value:
        raise ValueError(f"{field_name} must not be empty")
    return value


__all__ = [
    "TokenListArtifact",
    "TokenListReader",
    "TokenListWriter",
]
