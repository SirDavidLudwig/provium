from __future__ import annotations

import runpy
import sys

import pytest

from provium.__main__ import main


def test_package_launcher_delegates_to_installed_cli(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("provium_cli.main", lambda: 12)

    assert main() == 12


def test_package_launcher_explains_when_cli_is_not_installed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "importlib.util.find_spec",
        lambda name: None,
    )

    with pytest.raises(SystemExit) as error_info:
        main()

    assert str(error_info.value) == (
        "The Provium CLI is not installed. Install it with: "
        "python3 -m pip install provium-cli"
    )


def test_package_module_exits_with_launcher_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("provium_cli.main", lambda: 12)
    monkeypatch.delitem(sys.modules, "provium.__main__")

    with pytest.raises(SystemExit) as exit_info:
        runpy.run_module("provium.__main__", run_name="__main__")

    assert exit_info.value.code == 12
