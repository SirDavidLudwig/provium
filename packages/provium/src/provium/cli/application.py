"""Parser construction and command dispatch."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from provium import __version__

from .catalog import CommandCatalog
from .completion import enable_completion
from .discovery import discover_command_catalogs

_COMMAND_DESTINATION = "_provium_command"


def create_parser(catalog: CommandCatalog) -> argparse.ArgumentParser:
    """Create a parser containing the commands in a catalog."""
    parser = argparse.ArgumentParser(
        prog="provium",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"provium {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command_name", required=True)
    for command_type in catalog.commands.values():
        command = command_type()
        command_parser = subparsers.add_parser(
            command.name,
            help=command.help,
            add_help=command.add_help,
        )
        command.configure(command_parser)
        command_parser.set_defaults(**{_COMMAND_DESTINATION: command})
    return parser


def run(
    arguments: Sequence[str],
    *,
    catalog: CommandCatalog | None = None,
) -> int:
    """Parse arguments and execute the selected command."""
    selected_catalog = discover_command_catalogs() if catalog is None else catalog
    parser = create_parser(selected_catalog)
    enable_completion(parser)
    parsed = parser.parse_args(arguments)
    command = getattr(parsed, _COMMAND_DESTINATION)
    return command.execute(parsed)


def main() -> int:
    """Run the command-line interface with the process arguments."""
    return run(sys.argv[1:])


__all__ = ["create_parser", "main", "run"]
