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
from .procedure import (
    Procedure,
    ProcedureCatalog,
    ProcedureContract,
    ProcedureDefinition,
    ProcedureInputs,
    ProcedureOutputs,
    discover_procedure_catalogs,
    reset_procedure_discovery,
)

__version__ = version("provium")

__all__ = [
    "Artifact",
    "ArtifactCatalog",
    "ArtifactDefinition",
    "ArtifactReader",
    "ArtifactWriter",
    "Procedure",
    "ProcedureCatalog",
    "ProcedureContract",
    "ProcedureDefinition",
    "ProcedureInputs",
    "ProcedureOutputs",
    "__version__",
    "discover_artifact_catalogs",
    "discover_procedure_catalogs",
    "reset_artifact_discovery",
    "reset_procedure_discovery",
]
