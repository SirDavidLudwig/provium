from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from provium import (
    Artifact,
    ArtifactCatalog,
    ArtifactDefinition,
    ArtifactReader,
    ArtifactWriter,
    ProcedureCatalog,
)
from provium.cli import run
from provium.cli.commands.artifact import ArtifactCommand


class Reader(ArtifactReader):
    pass


class Writer(ArtifactWriter):
    pass


DEFINITION = ArtifactDefinition(
    "example.TransferV1", f"{__name__}:TransferArtifact", "Transferable data"
)


class TransferArtifact(Artifact[Reader, Writer]):
    definition = DEFINITION
    reader = Reader
    writer = Writer


def test_artifact_command_has_generic_help() -> None:
    assert ArtifactCommand.help == "Manage artifacts"


@pytest.fixture
def catalog(monkeypatch: pytest.MonkeyPatch) -> ArtifactCatalog:
    result = ArtifactCatalog()
    result.register(DEFINITION)
    monkeypatch.setattr(
        "provium.cli.commands.artifact.discover_artifact_catalogs", lambda: result
    )
    return result


def test_artifact_dump_calls_the_artifact_handler(
    catalog: ArtifactCatalog,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    del catalog
    source = tmp_path / "source.provium"
    destination = tmp_path / "dump"
    seen: list[tuple[object, Path]] = []
    monkeypatch.setattr(
        TransferArtifact, "dump", lambda reader, path: seen.append((reader, path))
    )
    monkeypatch.setattr(
        TransferArtifact,
        "bind_read",
        classmethod(lambda cls, path: _ReadBinding(path)),
    )
    monkeypatch.setattr(
        "provium.cli.commands.artifact.read_artifact_header",
        lambda path: SimpleNamespace(artifact_identifier=DEFINITION.identifier),
    )

    assert run(["artifact", "dump", str(source), str(destination)]) == 0
    assert seen == [(_ReadBinding.reader, destination)]
    assert _ReadBinding.reader.closed


def test_artifact_load_uses_an_internal_imperative_procedure(
    catalog: ArtifactCatalog,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    del catalog
    source = tmp_path / "dump"
    destination = tmp_path / "loaded.provium"
    events: list[object] = []
    monkeypatch.setattr(
        TransferArtifact, "load", lambda path, writer: events.append((path, writer))
    )
    monkeypatch.setattr(
        "provium.cli.commands.artifact.ImperativeProcedure", _ImperativeProcedure
    )
    monkeypatch.setattr(
        TransferArtifact,
        "bind_write",
        classmethod(lambda cls, path: _WriteBinding(path)),
    )

    assert (
        run(["artifact", "load", DEFINITION.identifier, str(source), str(destination)])
        == 0
    )
    assert _ImperativeProcedure.arguments[0] == "provium.builtin.LoadArtifactV1"
    assert _ImperativeProcedure.outputs == {"artifact": _WriteBinding(destination)}
    assert events == [(source, _ImperativeProcedure.writer)]
    assert ProcedureCatalog().definitions == {}


@pytest.mark.parametrize("action", ["dump", "load"])
def test_artifact_commands_report_missing_handlers(
    catalog: ArtifactCatalog,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    action: str,
) -> None:
    del catalog
    monkeypatch.setattr(TransferArtifact, action, None)
    monkeypatch.setattr(
        "provium.cli.commands.artifact.read_artifact_header",
        lambda path: SimpleNamespace(artifact_identifier=DEFINITION.identifier),
    )
    arguments = (
        ["artifact", "dump", "source", "destination"]
        if action == "dump"
        else ["artifact", "load", DEFINITION.identifier, "source", "destination"]
    )

    assert run(arguments) == 2
    assert f"does not define a {action} handler" in capsys.readouterr().err


def test_artifact_commands_report_an_unknown_artifact(
    catalog: ArtifactCatalog,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    del catalog
    monkeypatch.setattr(
        "provium.cli.commands.artifact.read_artifact_header",
        lambda path: SimpleNamespace(artifact_identifier="missing"),
    )

    assert run(["artifact", "dump", "source", "destination"]) == 2
    assert "unknown artifact: missing" in capsys.readouterr().err


class _ReadBinding:
    reader = MagicMock(closed=False)
    reader.__enter__.return_value = reader
    reader.__exit__.side_effect = lambda *args: setattr(
        _ReadBinding.reader, "closed", True
    )

    def __init__(self, path: object) -> None:
        self.path = path

    def open(self) -> Reader:
        return self.reader


class _WriteBinding:
    def __init__(self, path: object) -> None:
        self.path = path

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _WriteBinding) and self.path == other.path

    def open(self) -> object:
        return _ImperativeProcedure.writer


class _Execution:
    def __enter__(self):
        return self

    def __exit__(self, *arguments: object) -> None:
        del arguments


class _Writer:
    def __enter__(self):
        return self

    def __exit__(self, *arguments: object) -> None:
        del arguments


class _ImperativeProcedure:
    arguments: tuple[object, ...]
    outputs: object
    writer = _Writer()

    def __init__(self, *arguments: object) -> None:
        type(self).arguments = arguments

    def execute(self, *, outputs: object) -> _Execution:
        type(self).outputs = outputs
        execution = _Execution()
        execution.artifact = self.writer
        return execution
