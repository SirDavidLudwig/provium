"""Raw text artifact implementation."""

from provium import Artifact, ArtifactReader, ArtifactWriter


class RawTextReader(ArtifactReader):
    """Read UTF-8 text payloads."""

    def read(self) -> str:
        return self.body.read().decode("utf-8")


class RawTextWriter(ArtifactWriter):
    """Write UTF-8 text payloads."""

    def write(self, value: str) -> int:
        data = value.encode("utf-8")
        return self.body.write(data)


class RawTextArtifact(Artifact[RawTextReader, RawTextWriter]):
    reader = RawTextReader
    writer = RawTextWriter


__all__ = [
    "RawTextArtifact",
    "RawTextReader",
    "RawTextWriter",
]
