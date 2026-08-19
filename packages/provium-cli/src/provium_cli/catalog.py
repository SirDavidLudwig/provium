"""In-memory catalog of command classes."""

from __future__ import annotations

from collections.abc import Mapping
from inspect import isabstract
from types import MappingProxyType

from .command import Command


def _metadata(command: type[Command], field: str) -> str:
    value = getattr(command, field, None)
    if not isinstance(value, str) or not value:
        raise ValueError(f"command {field} must be a non-empty string")
    return value


class CommandCatalog:
    """Register and look up concrete command classes by name."""

    def __init__(self) -> None:
        self._commands: dict[str, type[Command]] = {}

    def register(self, command: type[Command]) -> type[Command]:
        """Register a command class and return it."""
        if not isinstance(command, type) or not issubclass(command, Command):
            raise TypeError("catalog entries must be a Command class")
        if isabstract(command):
            raise TypeError("catalog entries must be concrete Command classes")
        name = _metadata(command, "name")
        _metadata(command, "help")
        if name in self._commands:
            raise ValueError(f"command name is already registered: {name}")
        self._commands[name] = command
        return command

    def resolve(self, name: str) -> type[Command]:
        """Return the command class registered under a name."""
        return self._commands[name]

    @property
    def commands(self) -> Mapping[str, type[Command]]:
        """A read-only view of the registered commands."""
        return MappingProxyType(self._commands)


__all__ = ["CommandCatalog"]
