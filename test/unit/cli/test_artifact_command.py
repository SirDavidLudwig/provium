from __future__ import annotations

from io import StringIO
from pathlib import Path

from provium.artifact.transfer import (
    DumpInfo,
    DumpResult,
    LoadResult,
    VerificationResult,
)
from provium.cli.application import run
from provium.cli.commands.artifact import ArtifactCommand


def invoke(arguments: list[str]) -> tuple[int, str, str]:
    stdout, stderr = StringIO(), StringIO()
    status = run(
        arguments,
        stdout=stdout,
        stderr=stderr,
        commands=(ArtifactCommand(),),
    )
    return status, stdout.getvalue(), stderr.getvalue()


def test_dump_and_load_commands(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "provium.cli.commands.artifact.dump_artifact",
        lambda *args, **kwargs: DumpResult(tmp_path / "dump", "raw", {}),
    )
    status, stdout, _ = invoke(
        ["artifact", "dump", "input.pa", "dump", "--representation", "raw"]
    )
    assert status == 0
    assert "raw package" in stdout

    monkeypatch.setattr(
        "provium.cli.commands.artifact.load_artifact",
        lambda *args, **kwargs: LoadResult(tmp_path / "output.pa", "exact", True),
    )
    status, stdout, _ = invoke(["artifact", "load", "dump", "output.pa", "--overwrite"])
    assert status == 0
    assert "exact artifact" in stdout


def test_inspect_and_verify_commands(monkeypatch) -> None:
    monkeypatch.setattr(
        "provium.cli.commands.artifact.inspect_dump",
        lambda path: DumpInfo("example.TextV1", "abc", "custom", ({},)),
    )
    status, stdout, _ = invoke(["artifact", "inspect-dump", "dump"])
    assert status == 0
    assert "example.TextV1" in stdout
    assert "Transfer events: 1" in stdout

    monkeypatch.setattr(
        "provium.cli.commands.artifact.verify_dump",
        lambda path: VerificationResult(True, ()),
    )
    assert invoke(["artifact", "verify-dump", "dump"])[0:2] == (
        0,
        "Dump verified\n",
    )
    monkeypatch.setattr(
        "provium.cli.commands.artifact.verify_dump",
        lambda path: VerificationResult(False, ("bad digest",)),
    )
    status, _, stderr = invoke(["artifact", "verify-dump", "dump"])
    assert status == 1
    assert stderr == "bad digest\n"
