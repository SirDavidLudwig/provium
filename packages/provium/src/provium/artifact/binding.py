"""Immutable typed artifact path bindings."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .reader import ArtifactReader
from .writer import ArtifactWriter

if TYPE_CHECKING:
    from .definition import Artifact


@dataclass(frozen=True, slots=True)
class ArtifactReadBinding[ReaderT: ArtifactReader]:
    """Bind a concrete artifact reader type to a filesystem path."""

    artifact: type[Artifact[ReaderT, Any]]
    path: Path


@dataclass(frozen=True, slots=True)
class ArtifactWriteBinding[WriterT: ArtifactWriter]:
    """Bind a concrete artifact writer type to a filesystem path."""

    artifact: type[Artifact[Any, WriterT]]
    path: Path


__all__ = ["ArtifactReadBinding", "ArtifactWriteBinding"]
