from __future__ import annotations

import argparse

import pytest

from provium import __version__
from provium.cli import (
    Command,
    CommandCatalog,
    create_parser,
    main,
    run,
)


class ExampleCommand(Command):
    name = "example"
    help = "Run an example command"
    executions: list[str] = []

    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("value")

    def execute(self, arguments: argparse.Namespace) -> int:
        self.executions.append(arguments.value)
        return len(arguments.value)


class CommandArgumentCommand(Command):
    name = "command-argument"
    help = "Accept an argument named command"

    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("command")

    def execute(self, arguments: argparse.Namespace) -> int:
        return len(arguments.command)


@pytest.fixture
def catalog() -> CommandCatalog:
    result = CommandCatalog()
    result.register(ExampleCommand)
    return result


@pytest.fixture(autouse=True)
def clear_executions() -> None:
    ExampleCommand.executions.clear()


def test_parser_registers_catalog_commands(catalog: CommandCatalog) -> None:
    arguments = create_parser(catalog).parse_args(["example", "value"])

    assert isinstance(arguments._provium_command, ExampleCommand)
    assert arguments.value == "value"


def test_run_executes_the_selected_command(catalog: CommandCatalog) -> None:
    assert run(["example", "value"], catalog=catalog) == 5
    assert ExampleCommand.executions == ["value"]


def test_command_argument_named_command_does_not_overwrite_dispatch() -> None:
    catalog = CommandCatalog()
    catalog.register(CommandArgumentCommand)

    assert run(["command-argument", "value"], catalog=catalog) == 5


def test_run_discovers_commands_when_catalog_is_not_supplied(
    catalog: CommandCatalog,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def discover() -> CommandCatalog:
        nonlocal calls
        calls += 1
        return catalog

    monkeypatch.setattr("provium.cli.application.discover_command_catalogs", discover)

    assert run(["example", "hello"]) == 5
    assert calls == 1


def test_each_run_uses_a_fresh_command_instance(catalog: CommandCatalog) -> None:
    instances: list[ExampleCommand] = []

    class StatefulCommand(ExampleCommand):
        def __init__(self) -> None:
            instances.append(self)

    stateful_catalog = CommandCatalog()
    stateful_catalog.register(StatefulCommand)

    run(["example", "first"], catalog=stateful_catalog)
    run(["example", "second"], catalog=stateful_catalog)

    assert len(instances) == 2
    assert instances[0] is not instances[1]


def test_parser_requires_a_command() -> None:
    with pytest.raises(SystemExit) as exit_info:
        create_parser(CommandCatalog()).parse_args([])

    assert exit_info.value.code == 2


def test_parser_prints_the_installed_version(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exit_info:
        create_parser(CommandCatalog()).parse_args(["--version"])

    assert exit_info.value.code == 0
    assert capsys.readouterr().out == f"provium {__version__}\n"


def test_main_uses_process_arguments(monkeypatch: pytest.MonkeyPatch) -> None:
    received: list[list[str]] = []

    def fake_run(arguments: list[str]) -> int:
        received.append(arguments)
        return 9

    monkeypatch.setattr("provium.cli.application.run", fake_run)
    monkeypatch.setattr("provium.cli.application.sys.argv", ["provium", "example"])

    assert main() == 9
    assert received == [["example"]]
