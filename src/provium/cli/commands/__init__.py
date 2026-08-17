"""Built-in CLI command registry."""

from .artifact import ArtifactCommand
from .graph import GraphCommand
from .inspect import InspectCommand

COMMANDS = (InspectCommand(), GraphCommand(), ArtifactCommand())

__all__ = ["COMMANDS"]
