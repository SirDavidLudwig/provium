"""Artifact definition interfaces."""

from .binding import ArtifactReadBinding, ArtifactWriteBinding
from .catalog import ArtifactCatalog
from .definition import Artifact, ArtifactDefinition
from .discovery import discover_artifact_catalogs, reset_artifact_discovery
from .header import ArtifactHeader, decode_header, encode_header, read_artifact_header
from .reader import ArtifactReader
from .region import BodyRegion
from .staging import StagedArtifact, stage_artifact
from .writer import ArtifactWriter

__all__ = [
    "Artifact",
    "ArtifactCatalog",
    "ArtifactDefinition",
    "ArtifactHeader",
    "ArtifactReadBinding",
    "ArtifactReader",
    "BodyRegion",
    "StagedArtifact",
    "decode_header",
    "ArtifactWriter",
    "ArtifactWriteBinding",
    "discover_artifact_catalogs",
    "encode_header",
    "read_artifact_header",
    "reset_artifact_discovery",
    "stage_artifact",
]
