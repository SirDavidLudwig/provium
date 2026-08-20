from __future__ import annotations

import runpy
import sys

import pytest

from provium.__main__ import main


def test_package_launcher_delegates_to_bundled_cli(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("provium.cli.main", lambda: 12)

    assert main() == 12


def test_package_module_exits_with_cli_main_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("provium.cli.main", lambda: 12)
    monkeypatch.delitem(sys.modules, "provium.__main__")

    with pytest.raises(SystemExit) as exit_info:
        runpy.run_module("provium.__main__", run_name="__main__")

    assert exit_info.value.code == 12


def test_cli_package_module_exits_with_cli_main_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("provium.cli.main", lambda: 12)

    with pytest.raises(SystemExit) as exit_info:
        runpy.run_module("provium.cli.__main__", run_name="__main__")

    assert exit_info.value.code == 12
