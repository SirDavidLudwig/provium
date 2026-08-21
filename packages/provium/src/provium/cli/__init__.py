# PYTHON_ARGCOMPLETE_OK
"""Provium's command-line interface and command plugin system."""

from importlib.metadata import version

from .application import create_parser, main, run
from .catalog import CommandCatalog
from .command import Command
from .discovery import discover_command_catalogs, reset_command_discovery

__version__ = version("provium")

__all__ = [
    "Command",
    "CommandCatalog",
    "__version__",
    "create_parser",
    "discover_command_catalogs",
    "main",
    "reset_command_discovery",
    "run",
]
