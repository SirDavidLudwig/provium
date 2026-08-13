"""Shared command contracts and execution context."""

from __future__ import annotations

from argparse import ArgumentParser, Namespace
from dataclasses import dataclass
from typing import Protocol, TextIO


@dataclass(frozen=True, slots=True)
class CommandContext:
    """Process streams available to a command."""

    stdout: TextIO
    stderr: TextIO


class Command(Protocol):
    """A self-contained CLI subcommand."""

    name: str
    help: str

    def configure(self, parser: ArgumentParser) -> None: ...

    def execute(self, arguments: Namespace, context: CommandContext) -> int: ...


__all__ = ["Command", "CommandContext"]

