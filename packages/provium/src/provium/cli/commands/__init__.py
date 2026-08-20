"""Commands provided by the Provium CLI distribution."""

from ..catalog import CommandCatalog
from .artifact import ArtifactCommand
from .procedure import ExecuteCommand, ProcedureCommand

catalog = CommandCatalog()
catalog.register(ProcedureCommand)
catalog.register(ExecuteCommand)
catalog.register(ArtifactCommand)

__all__ = ["catalog"]
