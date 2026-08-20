"""Disk-backed staging for artifact outputs."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, BinaryIO, cast
from uuid import uuid4

from provium.context import current_context

from .binding import ArtifactWriteBinding
from .header import ArtifactHeader
from .region import BodyRegion
from .writer import ArtifactWriter

if TYPE_CHECKING:
    from provium.session import Session


class StagedArtifact[WriterT: ArtifactWriter]:
    """Own one unpublished temporary container and its typed writer."""

    def __init__(
        self,
        destination: Path,
        temporary_path: Path,
        stream: BinaryIO,
        writer: WriterT,
    ) -> None:
        self.destination = destination
        self.temporary_path = temporary_path
        self._stream = stream
        self.writer = writer
        self._aborted = False

    @property
    def aborted(self) -> bool:
        """Return whether this staged output has been abandoned."""
        return self._aborted

    def abort(self) -> None:
        """Close and remove this unpublished output."""
        if self._aborted:
            return
        try:
            self.writer.close()
        finally:
            self._stream.close()
            self.temporary_path.unlink(missing_ok=True)
            self._aborted = True

    def close(self) -> None:
        """Abandon the output when its owning session closes."""
        self.abort()


def stage_artifact[WriterT: ArtifactWriter](
    binding: ArtifactWriteBinding[WriterT],
    metadata: ArtifactHeader,
    owner: Session,
) -> StagedArtifact[WriterT]:
    """Create an adjacent temporary container for one typed output."""
    _validate_staging(binding, metadata, owner)
    destination = binding.path
    temporary_path = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
    stream = temporary_path.open("x+b")
    try:
        _reserve_body_offset(stream, metadata.body_offset)
        region = BodyRegion(
            stream,
            metadata.body_offset,
            0,
            owner,
            writable=True,
            close_stream=True,
        )
        writer_type = cast(
            type[WriterT],
            getattr(binding.artifact, "writer"),
        )
        writer = writer_type(region, metadata)
        staged = StagedArtifact(destination, temporary_path, stream, writer)
        owner.manage(staged)
    except BaseException:
        stream.close()
        temporary_path.unlink(missing_ok=True)
        raise
    return staged


def _validate_staging(
    binding: ArtifactWriteBinding[Any],
    metadata: ArtifactHeader,
    owner: Session,
) -> None:
    if not owner.active or current_context() is not owner:
        raise RuntimeError("artifact staging requires the active session")
    if not isinstance(metadata, ArtifactHeader):
        raise TypeError("metadata must be an ArtifactHeader")
    if metadata.artifact_identifier != binding.artifact.definition.identifier:
        raise ValueError("metadata artifact identifier does not match the binding")
    if metadata.body_length != 0:
        raise ValueError("staged artifact metadata must have an empty body")


def _reserve_body_offset(stream: BinaryIO, body_offset: int) -> None:
    stream.seek(body_offset - 1)
    stream.write(b"\0")
    stream.flush()


__all__ = ["StagedArtifact", "stage_artifact"]
