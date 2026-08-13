from importlib.metadata import version

from .artifact import Artifact, open_artifact
from .artifact.catalog import ArtifactCatalog, ArtifactRegistration
from .artifact.discovery import discover_catalogs, reset_discovery
from .artifact.header import ArtifactHeader, decode_header, encode_header
from .artifact.reader import ArtifactReader
from .artifact.writer import ArtifactWriter
from .config import ConfigCodec, ConfigurationSnapshot, JsonValue
from .procedure import ExecutionContext, Procedure, current_execution
from .provenance import (
    ArtifactLineage,
    ArtifactRecord,
    ArtifactReference,
    ProcedureExecutionRecord,
    ProcedureRecord,
)

__version__ = version("provium")

__all__ = [
    "Artifact",
    "ArtifactCatalog",
    "ArtifactHeader",
    "ArtifactLineage",
    "ArtifactReader",
    "ArtifactRecord",
    "ArtifactReference",
    "ArtifactRegistration",
    "ArtifactWriter",
    "ConfigCodec",
    "ConfigurationSnapshot",
    "ExecutionContext",
    "JsonValue",
    "Procedure",
    "ProcedureExecutionRecord",
    "ProcedureRecord",
    "__version__",
    "decode_header",
    "discover_catalogs",
    "encode_header",
    "current_execution",
    "open_artifact",
    "reset_discovery",
]
