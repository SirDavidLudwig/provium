"""Tests for CLI error diagnostics."""

from __future__ import annotations

import pytest

from provium.cli.errors import print_cli_error


def _nested_failure() -> None:
    def missing_value() -> None:
        raise KeyError("missing plugin value")

    try:
        missing_value()
    except KeyError as error:
        raise TypeError("plugin catalog is invalid") from error


def test_cli_error_identifies_operation_type_origin_and_cause(
    capsys: pytest.CaptureFixture[str],
) -> None:
    try:
        _nested_failure()
    except TypeError as error:
        assert print_cli_error("discovering artifact plugins", error) == 2

    diagnostic = capsys.readouterr().err
    assert "error: discovering artifact plugins failed" in diagnostic
    assert "TypeError" in diagnostic
    assert "test_error_formatting._nested_failure" in diagnostic
    assert "plugin catalog is invalid" in diagnostic
    assert "caused by KeyError" in diagnostic
    assert "missing plugin value" in diagnostic


def test_cli_error_handles_an_exception_without_a_traceback(
    capsys: pytest.CaptureFixture[str],
) -> None:
    context = "executing procedure 'example.TaskV1'"
    assert print_cli_error(context, ValueError("bad")) == 2

    diagnostic = capsys.readouterr().err
    assert "error: executing procedure 'example.TaskV1' failed" in diagnostic
    assert "ValueError: bad" in diagnostic
    assert "raised at" not in diagnostic
