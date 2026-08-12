from importlib.metadata import version

from .provenance import (
    ArtifactLineage,
    ArtifactRecord,
    ArtifactReference,
    ProcedureExecutionRecord,
    ProcedureRecord,
)

__version__ = version("provium")

__all__ = [
    "ArtifactLineage",
    "ArtifactRecord",
    "ArtifactReference",
    "ProcedureExecutionRecord",
    "ProcedureRecord",
    "__version__",
]
