"""Provium's command-line entry point."""

from .catalog import CommandCatalog
from .command import Command
from .discovery import discover_command_catalogs, reset_command_discovery


def main() -> int:
    """Run the Provium command-line interface."""
    return 0


__all__ = [
    "Command",
    "CommandCatalog",
    "discover_command_catalogs",
    "main",
    "reset_command_discovery",
]
