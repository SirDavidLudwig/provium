"""Built-in CLI command registry."""

from .graph import GraphCommand
from .inspect import InspectCommand

COMMANDS = (InspectCommand(), GraphCommand())

__all__ = ["COMMANDS"]
