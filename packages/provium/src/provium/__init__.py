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
    ProcedureConfig,
    ProcedureContract,
    ProcedureDefinition,
    ProcedureInputs,
    ProcedureOutputs,
    compose_configuration,
    discover_procedure_catalogs,
    load_json_configuration,
    load_yaml_configuration,
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
    "ProcedureConfig",
    "ProcedureContract",
    "ProcedureDefinition",
    "ProcedureInputs",
    "ProcedureOutputs",
    "__version__",
    "compose_configuration",
    "discover_artifact_catalogs",
    "discover_procedure_catalogs",
    "load_json_configuration",
    "load_yaml_configuration",
    "reset_artifact_discovery",
    "reset_procedure_discovery",
]
