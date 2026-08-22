"""Commands provided by the Provium CLI distribution."""

from ..catalog import CommandCatalog
from .artifact import ArtifactCommand
from .execute import ExecuteCommand
from .graph import GraphCommand

catalog = CommandCatalog()
catalog.register(ExecuteCommand)
catalog.register(ArtifactCommand)
catalog.register(GraphCommand)

__all__ = ["catalog"]
