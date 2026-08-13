from __future__ import annotations

import io
import sys

import pytest

from provium.cli.application import create_parser, main, run
from provium.cli.command import CommandContext


class ExampleCommand:
    name = "example"
    help = "Run the example"

    def configure(self, parser: object) -> None:
        parser.add_argument("value")

    def execute(self, arguments: object, context: CommandContext) -> int:
        print(arguments.value, file=context.stdout)
        return 7


def test_parser_registers_and_selects_commands() -> None:
    command = ExampleCommand()

    arguments = create_parser((command,)).parse_args(["example", "hello"])

    assert arguments.command is command
    assert arguments.value == "hello"


def test_run_dispatches_with_injected_streams() -> None:
    stdout = io.StringIO()
    stderr = io.StringIO()

    result = run(
        ["example", "hello"],
        stdout=stdout,
        stderr=stderr,
        commands=(ExampleCommand(),),
    )

    assert result == 7
    assert stdout.getvalue() == "hello\n"
    assert stderr.getvalue() == ""


@pytest.mark.parametrize(
    "error",
    [OSError("unreadable"), ValueError("invalid"), RuntimeError("unavailable")],
)
def test_run_reports_expected_command_errors(error: Exception) -> None:
    class FailingCommand(ExampleCommand):
        def execute(self, arguments: object, context: CommandContext) -> int:
            raise error

    stderr = io.StringIO()

    result = run(
        ["example", "hello"],
        stdout=io.StringIO(),
        stderr=stderr,
        commands=(FailingCommand(),),
    )

    assert result == 1
    assert stderr.getvalue() == f"provium: {error}\n"


def test_main_uses_process_arguments_and_streams(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stdout = io.StringIO()
    stderr = io.StringIO()
    monkeypatch.setattr(sys, "argv", ["provium", "example", "value"])
    monkeypatch.setattr(sys, "stdout", stdout)
    monkeypatch.setattr(sys, "stderr", stderr)
    monkeypatch.setattr(
        "provium.cli.application.COMMANDS",
        (ExampleCommand(),),
    )

    assert main() == 7
    assert stdout.getvalue() == "value\n"
    assert stderr.getvalue() == ""
