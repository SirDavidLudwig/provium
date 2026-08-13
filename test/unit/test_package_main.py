from __future__ import annotations

import runpy

import pytest


def test_package_module_exits_with_cli_main_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("provium.cli.main", lambda: 14)

    with pytest.raises(SystemExit, match="14"):
        runpy.run_module("provium", run_name="__main__")
