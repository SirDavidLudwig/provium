from __future__ import annotations

import runpy

import pytest


def test_package_module_exits_with_cli_main_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("provium.cli.main", lambda: 12)

    with pytest.raises(SystemExit) as exit_info:
        runpy.run_module("provium.__main__", run_name="__main__")

    assert exit_info.value.code == 12
