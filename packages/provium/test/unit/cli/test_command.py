from __future__ import annotations

import argparse

import pytest

from provium.cli import Command


def test_command_is_abstract() -> None:
    with pytest.raises(TypeError):
        Command()


def test_concrete_command_can_configure_and_execute() -> None:
    class ExampleCommand(Command):
        name = "example"
        help = "Run an example command"

        def configure(self, parser: argparse.ArgumentParser) -> None:
            parser.add_argument("value")

        def execute(self, arguments: argparse.Namespace) -> int:
            return len(arguments.value)

    command = ExampleCommand()
    parser = argparse.ArgumentParser()
    command.configure(parser)

    assert command.name == "example"
    assert command.help == "Run an example command"
    assert command.add_help is True
    assert command.execute(parser.parse_args(["value"])) == 5
