"""Commands provided by the Provium CLI distribution."""

from ..catalog import CommandCatalog
from .artifact import ArtifactCommand
from .execute import ExecuteCommand

catalog = CommandCatalog()
catalog.register(ExecuteCommand)
catalog.register(ArtifactCommand)

__all__ = ["catalog"]
