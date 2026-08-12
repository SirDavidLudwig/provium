"""Base class for typed artifact readers."""

from __future__ import annotations

from typing import Self

from .header import ArtifactHeader
from .provenance import ArtifactLineage
from .region import BodyRegion


class ArtifactReader:
    """Own metadata and bounded body access for a concrete artifact reader."""

    def __init__(self, body: BodyRegion, metadata: ArtifactHeader) -> None:
        if not isinstance(body, BodyRegion):
            raise TypeError("body must be a BodyRegion")
        if not isinstance(metadata, ArtifactHeader):
            raise TypeError("metadata must be an ArtifactHeader")
        self._body = body
        self._metadata = metadata

    @property
    def metadata(self) -> ArtifactHeader:
        return self._metadata

    @property
    def identity(self) -> str:
        return self._metadata.artifact_identity

    @property
    def artifact_identifier(self) -> str:
        return self._metadata.artifact_identifier

    @property
    def lineage(self) -> ArtifactLineage:
        return self._metadata.lineage

    @property
    def body(self) -> BodyRegion:
        self._body.check_access()
        return self._body

    @property
    def closed(self) -> bool:
        return self._body.closed

    def close(self) -> None:
        self._body.close()

    def __enter__(self) -> Self:
        self._body.check_access()
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.close()


__all__ = ["ArtifactReader"]
