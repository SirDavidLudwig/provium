"""Provium's command-line entry point."""

from .application import create_parser, main, run
from .catalog import CommandCatalog
from .command import Command
from .discovery import discover_command_catalogs, reset_command_discovery

__all__ = [
    "Command",
    "CommandCatalog",
    "create_parser",
    "discover_command_catalogs",
    "main",
    "reset_command_discovery",
    "run",
]
