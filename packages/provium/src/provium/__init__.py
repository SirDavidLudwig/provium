"""Core functionality for the Provium platform."""

from importlib.metadata import version

from .artifact import (
    Artifact,
    ArtifactCatalog,
    ArtifactDefinition,
    ArtifactReader,
    ArtifactWriter,
    discover_artifact_catalogs,
    reset_artifact_discovery,
)

__version__ = version("provium")

__all__ = [
    "Artifact",
    "ArtifactCatalog",
    "ArtifactDefinition",
    "ArtifactReader",
    "ArtifactWriter",
    "__version__",
    "discover_artifact_catalogs",
    "reset_artifact_discovery",
]
