"""CLI integration tests for real procedure inspection."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from support.provium_test_pipeline.contracts import TRANSFORM_PROCEDURE

from provium.cli import run
from provium.cli.commands import catalog as command_catalog


def test_procedure_list_and_show_use_real_catalog_metadata(
    discovered_pipeline: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    del discovered_pipeline
    assert run(["procedure", "list"], catalog=command_catalog) == 0
    captured = capsys.readouterr()
    lines = captured.out.splitlines()
    assert lines == sorted(lines)
    assert "test.SourceTextV1\tSource text" in lines
    assert "test.TransformTextV1\tTransform text" in lines
    assert captured.err == ""

    assert (
        run(
            ["procedure", "show", TRANSFORM_PROCEDURE.identifier],
            catalog=command_catalog,
        )
        == 0
    )
    captured = capsys.readouterr()
    assert "Transform text (test.TransformTextV1)" in captured.out
    assert "Combine several text inputs" in captured.out
    assert TRANSFORM_PROCEDURE.invocation_synopsis in captured.out
    assert "setup: test.TextV1 [1..1]" in captured.out
    assert "optional: test.TextV1 [0..1]" in captured.out
    assert "repeated: test.TextV1 [1..4]" in captured.out
    assert "transformed: test.TextV1 [1..1]" in captured.out
    assert '"prefix"' in captured.out
    assert captured.err == ""


def test_quick_show_is_lazy_and_resolve_imports_implementations(
    pipeline_distribution: Path,
    tmp_path: Path,
) -> None:
    core_root = Path(__file__).parents[4] / "provium"
    cli_root = Path(__file__).parents[3]
    pythonpath = os.pathsep.join(
        (
            str(pipeline_distribution),
            str(core_root / "src"),
            str(core_root / "test"),
            str(cli_root / "src"),
        )
    )
    scenarios = (
        ([], tmp_path / "quick.log", False),
        (["--resolve"], tmp_path / "resolved.log", True),
    )
    for extra_arguments, sentinel, expect_import in scenarios:
        environment = os.environ.copy()
        environment["PYTHONPATH"] = pythonpath
        environment["PROVIUM_TEST_IMPORT_SENTINEL"] = str(sentinel)
        script = f"""
from pathlib import Path
from provium.cli import run
from provium.cli.commands import catalog

status = run(
    ["procedure", "show", "test.TransformTextV1", *{extra_arguments!r}],
    catalog=catalog,
)
assert status == 0
sentinel = Path({str(sentinel)!r})
assert sentinel.exists() is {expect_import!r}
if sentinel.exists():
    assert sentinel.read_text().splitlines() == ["procedures", "artifacts"]
"""
        subprocess.run(
            [sys.executable, "-c", script],
            check=True,
            cwd=cli_root,
            env=environment,
            capture_output=True,
            text=True,
        )


def test_unknown_procedure_reports_only_a_clear_stderr_error(
    discovered_pipeline: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    del discovered_pipeline
    assert (
        run(
            ["procedure", "show", "test.MissingV1"],
            catalog=command_catalog,
        )
        == 2
    )
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "error: unknown procedure: test.MissingV1\n"
