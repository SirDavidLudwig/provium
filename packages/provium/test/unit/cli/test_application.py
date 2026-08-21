from __future__ import annotations

import argparse
import tomllib
from pathlib import Path

import pytest

from provium import __version__
from provium.cli import (
    Command,
    CommandCatalog,
    create_parser,
    main,
    run,
)
from provium.cli.completion import enable_completion


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


def test_run_enables_completion_before_parsing(
    catalog: CommandCatalog,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    completed: list[argparse.ArgumentParser] = []
    monkeypatch.setattr(
        "provium.cli.application.enable_completion",
        lambda parser: completed.append(parser),
    )

    assert run(["example", "value"], catalog=catalog) == 5
    assert len(completed) == 1
    assert completed[0].prog == "provium"


def test_completion_activation_tolerates_a_dependency_omitted_install(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing(name: str) -> object:
        raise ModuleNotFoundError(name)

    monkeypatch.setattr("provium.cli.completion.import_module", missing)

    assert enable_completion(argparse.ArgumentParser()) is None


def test_distribution_declares_and_marks_argcomplete_support() -> None:
    project = Path(__file__).parents[3]
    configuration = tomllib.loads((project / "pyproject.toml").read_text())
    cli_module = project / "src" / "provium" / "cli" / "__init__.py"

    assert "argcomplete>=3,<4" in configuration["project"]["dependencies"]
    assert cli_module.read_text().splitlines()[0] == "# PYTHON_ARGCOMPLETE_OK"


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


def test_main_reports_unhandled_cli_failure_with_origin(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail(arguments: list[str]) -> int:
        del arguments
        raise TypeError("entry point 'broken' did not expose a command catalog")

    monkeypatch.setattr("provium.cli.application.run", fail)
    monkeypatch.setattr("provium.cli.application.sys.argv", ["provium", "example"])

    assert main() == 2
    diagnostic = capsys.readouterr().err
    assert "running the Provium CLI failed" in diagnostic
    assert "TypeError" in diagnostic
    assert (
        "test_main_reports_unhandled_cli_failure_with_origin.<locals>.fail"
        in diagnostic
    )
    assert "entry point 'broken'" in diagnostic
