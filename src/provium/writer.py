"""Base class for typed artifact writers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Self

from .header import ArtifactHeader
from .provenance import ArtifactLineage
from .region import BodyRegion


class ArtifactWriter:
    """Own writable body access separately from final container completion."""

    def __init__(
        self,
        body: BodyRegion,
        metadata: ArtifactHeader,
        *,
        finalizer: Callable[[ArtifactWriter], None] | None = None,
    ) -> None:
        if not isinstance(body, BodyRegion):
            raise TypeError("body must be a BodyRegion")
        if not isinstance(metadata, ArtifactHeader):
            raise TypeError("metadata must be an ArtifactHeader")
        self._body = body
        self._metadata = metadata
        self._finalizer = finalizer
        self._container_finalized = False

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

    @property
    def body_complete(self) -> bool:
        return self.closed

    @property
    def container_finalized(self) -> bool:
        return self._container_finalized

    def close(self) -> None:
        self._body.close()

    def finalize(self) -> None:
        if self._container_finalized:
            return
        if not self.closed:
            self.close()
        else:
            self._body.check_context()
        if self._finalizer is not None:
            self._finalizer(self)
        self._container_finalized = True

    def __enter__(self) -> Self:
        self._body.check_access()
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.close()

    def _replace_metadata(self, metadata: ArtifactHeader) -> None:
        """Replace provisional metadata during owning-context finalization."""
        self._metadata = metadata


__all__ = ["ArtifactWriter"]
