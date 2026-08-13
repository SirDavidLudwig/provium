from __future__ import annotations

import runpy

import pytest


def test_module_exits_with_main_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("provium.cli.main", lambda: 12)

    with pytest.raises(SystemExit, match="12"):
        runpy.run_module("provium.cli", run_name="__main__")
