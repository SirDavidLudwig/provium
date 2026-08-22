"""Tests for provenance graph CLI commands."""

from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from provium import ArtifactLineage
from provium.cli.commands.graph import GraphCommand


class TTYInput(io.StringIO):
    def isatty(self) -> bool:
        return True


def parse(*arguments: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    command = GraphCommand()
    command.configure(parser)
    return parser.parse_args(arguments)


def test_render_appends_png_and_passes_extension_to_backend(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "lineage"
    calls: list[tuple[str, str, bool, bool, bool]] = []
    monkeypatch.setattr(
        "provium.cli.commands.graph.read_artifact_header",
        lambda path: SimpleNamespace(lineage=ArtifactLineage()),
    )
    monkeypatch.setattr(
        "provium.cli.commands.graph.render_lineage",
        lambda lineage, *, format, backend, show_artifact_identities,
        show_procedure_versions, show_execution_identities: calls.append(
            (
                format,
                backend,
                show_artifact_identities,
                show_procedure_versions,
                show_execution_identities,
            )
        )
        or b"image",
    )

    assert GraphCommand().execute(
        parse(
            "render",
            "artifact.pvm",
            str(output),
            "--backend",
            "mermaid",
            "-a",
            "-p",
            "-e",
        )
    ) == 0
    assert not output.exists()
    assert output.with_suffix(".png").read_bytes() == b"image"
    assert calls == [("png", "mermaid", True, True, True)]


def test_render_passes_arbitrary_extension_to_backend(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "lineage.custom"
    monkeypatch.setattr(
        "provium.cli.commands.graph.read_artifact_header",
        lambda path: SimpleNamespace(lineage=ArtifactLineage()),
    )
    formats: list[str] = []
    monkeypatch.setattr(
        "provium.cli.commands.graph.render_lineage",
        lambda lineage, *, format, backend, **kwargs: formats.append(format)
        or b"image",
    )

    assert GraphCommand().execute(parse("render", "artifact.pvm", str(output))) == 0
    assert formats == ["custom"]


def test_source_writes_stdout_or_exact_optional_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        "provium.cli.commands.graph.read_artifact_header",
        lambda path: SimpleNamespace(lineage=ArtifactLineage()),
    )
    monkeypatch.setattr(
        "provium.cli.commands.graph.lineage_to_dot", lambda lineage: "dot source\n"
    )
    monkeypatch.setattr(
        "provium.cli.commands.graph.lineage_to_mermaid",
        lambda lineage: "mermaid source\n",
    )

    assert GraphCommand().execute(parse("source", "artifact.pvm", "dot")) == 0
    assert capsys.readouterr().out == "dot source\n"

    output = tmp_path / "source-without-extension"
    assert GraphCommand().execute(
        parse("source", "artifact.pvm", "mermaid", str(output))
    ) == 0
    assert output.read_text() == "mermaid source\n"


def test_source_forwards_hash_display_flags(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "lineage.dot"
    options: list[dict[str, bool]] = []
    monkeypatch.setattr(
        "provium.cli.commands.graph.read_artifact_header",
        lambda path: SimpleNamespace(lineage=ArtifactLineage()),
    )
    monkeypatch.setattr(
        "provium.cli.commands.graph.lineage_to_dot",
        lambda lineage, **kwargs: options.append(kwargs) or "source",
    )

    assert GraphCommand().execute(
        parse(
            "source",
            "artifact.pvm",
            "dot",
            str(output),
            "-a",
            "-e",
        )
    ) == 0
    assert options == [
        {
            "show_artifact_identities": True,
            "show_execution_identities": True,
        }
    ]


def test_existing_output_prompts_on_stderr_and_honors_response(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "lineage.dot"
    output.write_text("original")
    monkeypatch.setattr(
        "provium.cli.commands.graph.read_artifact_header",
        lambda path: SimpleNamespace(lineage=ArtifactLineage()),
    )
    monkeypatch.setattr(
        "provium.cli.commands.graph.lineage_to_dot", lambda lineage: "replacement"
    )
    monkeypatch.setattr(sys, "stdin", TTYInput("n\n"))

    assert GraphCommand().execute(
        parse("source", "artifact.pvm", "dot", str(output))
    ) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Overwrite" in captured.err
    assert output.read_text() == "original"

    monkeypatch.setattr(sys, "stdin", TTYInput("y\n"))
    assert GraphCommand().execute(
        parse("source", "artifact.pvm", "dot", str(output))
    ) == 0
    assert output.read_text() == "replacement"


def test_force_overwrites_and_noninteractive_input_fails_without_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "lineage.mmd"
    output.write_text("original")
    monkeypatch.setattr(
        "provium.cli.commands.graph.read_artifact_header",
        lambda path: SimpleNamespace(lineage=ArtifactLineage()),
    )
    monkeypatch.setattr(
        "provium.cli.commands.graph.lineage_to_mermaid", lambda lineage: "replacement"
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO("y\n"))

    assert GraphCommand().execute(
        parse("source", "artifact.pvm", "mermaid", str(output))
    ) == 2
    assert output.read_text() == "original"

    assert GraphCommand().execute(
        parse("source", "artifact.pvm", "mermaid", str(output), "-y")
    ) == 0
    assert output.read_text() == "replacement"
