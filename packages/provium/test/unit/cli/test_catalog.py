from __future__ import annotations

import argparse
from collections.abc import Mapping

import pytest

from provium.cli import Command, CommandCatalog


class ExampleCommand(Command):
    name = "example"
    help = "Run an example command"

    def configure(self, parser: argparse.ArgumentParser) -> None:
        pass

    def execute(self, arguments: argparse.Namespace) -> int:
        return 0


def test_registers_and_resolves_command_classes() -> None:
    catalog = CommandCatalog()

    registered = catalog.register(ExampleCommand)

    assert registered is ExampleCommand
    assert catalog.resolve("example") is ExampleCommand
    assert catalog.commands == {"example": ExampleCommand}
    assert isinstance(catalog.commands, Mapping)


def test_commands_view_is_read_only() -> None:
    catalog = CommandCatalog()
    catalog.register(ExampleCommand)

    with pytest.raises(TypeError):
        catalog.commands["other"] = ExampleCommand  # type: ignore[index]


def test_unknown_command_is_not_registered() -> None:
    with pytest.raises(KeyError):
        CommandCatalog().resolve("missing")


def test_rejects_values_that_are_not_command_classes() -> None:
    catalog = CommandCatalog()

    with pytest.raises(TypeError, match="Command class"):
        catalog.register(object)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="Command class"):
        catalog.register(ExampleCommand())  # type: ignore[arg-type]


def test_rejects_abstract_command_classes() -> None:
    with pytest.raises(TypeError, match="concrete"):
        CommandCatalog().register(Command)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", ""),
        ("name", 1),
        ("help", ""),
        ("help", 1),
    ],
)
def test_rejects_invalid_command_metadata(field: str, value: object) -> None:
    attributes = {field: value}
    InvalidCommand = type("InvalidCommand", (ExampleCommand,), attributes)

    with pytest.raises(ValueError, match=field):
        CommandCatalog().register(InvalidCommand)


def test_rejects_missing_command_metadata() -> None:
    class MissingMetadataCommand(Command):
        def configure(self, parser: argparse.ArgumentParser) -> None:
            pass

        def execute(self, arguments: argparse.Namespace) -> int:
            return 0

    with pytest.raises(ValueError, match="name"):
        CommandCatalog().register(MissingMetadataCommand)


def test_rejects_duplicate_command_names() -> None:
    class DuplicateCommand(ExampleCommand):
        pass

    catalog = CommandCatalog()
    catalog.register(ExampleCommand)

    with pytest.raises(ValueError, match="already registered"):
        catalog.register(DuplicateCommand)

    assert catalog.resolve("example") is ExampleCommand
