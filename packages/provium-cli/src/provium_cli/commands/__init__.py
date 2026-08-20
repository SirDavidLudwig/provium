"""Commands provided by the Provium CLI distribution."""

from ..catalog import CommandCatalog
from .procedure import ExecuteCommand, ProcedureCommand

catalog = CommandCatalog()
catalog.register(ProcedureCommand)
catalog.register(ExecuteCommand)

__all__ = ["catalog"]
