"""Artifact definition interfaces."""

from .binding import ArtifactReadBinding, ArtifactWriteBinding
from .catalog import ArtifactCatalog
from .definition import Artifact, ArtifactDefinition
from .discovery import discover_artifact_catalogs, reset_artifact_discovery
from .reader import ArtifactReader
from .region import BodyRegion
from .writer import ArtifactWriter

__all__ = [
    "Artifact",
    "ArtifactCatalog",
    "ArtifactDefinition",
    "ArtifactReadBinding",
    "ArtifactReader",
    "BodyRegion",
    "ArtifactWriter",
    "ArtifactWriteBinding",
    "discover_artifact_catalogs",
    "reset_artifact_discovery",
]
