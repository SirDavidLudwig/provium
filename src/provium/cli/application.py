"""Parser construction and command dispatch."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from typing import TextIO

from .command import Command, CommandContext
from .commands import COMMANDS


def create_parser(commands: Sequence[Command]) -> argparse.ArgumentParser:
    """Create the root parser and register the supplied commands."""
    parser = argparse.ArgumentParser(prog="provium")
    subparsers = parser.add_subparsers(required=True)
    for command in commands:
        command_parser = subparsers.add_parser(command.name, help=command.help)
        command.configure(command_parser)
        command_parser.set_defaults(command=command)
    return parser


def run(
    argv: Sequence[str],
    *,
    stdout: TextIO,
    stderr: TextIO,
    commands: Sequence[Command] = COMMANDS,
) -> int:
    """Parse arguments and execute one command."""
    arguments = create_parser(commands).parse_args(argv)
    context = CommandContext(stdout=stdout, stderr=stderr)
    try:
        return arguments.command.execute(arguments, context)
    except (OSError, RuntimeError, ValueError) as error:
        print(f"provium: {error}", file=stderr)
        return 1


def main() -> int:
    """Run the CLI using the current process arguments and streams."""
    return run(sys.argv[1:], stdout=sys.stdout, stderr=sys.stderr, commands=COMMANDS)


__all__ = ["create_parser", "main", "run"]
