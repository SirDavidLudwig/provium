from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from provium import (
    Artifact,
    ArtifactCatalog,
    ArtifactDefinition,
    ArtifactReader,
    ArtifactReference,
    ArtifactWriter,
    Procedure,
    decode_header,
    discover_catalogs,
    open_artifact,
    reset_discovery,
)


class TextReader(ArtifactReader):
    def read_text(self) -> str:
        return self.body.read().decode("utf-8")


class TextWriter(ArtifactWriter):
    def write_text(self, value: str) -> None:
        self.body.write(value.encode("utf-8"))


TextArtifact = Artifact("example.TextV1", "Text", TextReader, TextWriter)


def public_catalog() -> ArtifactCatalog:
    catalog = ArtifactCatalog()
    catalog.register(
        ArtifactDefinition("example.TextV1", f"{__name__}:TextArtifact", "Text.")
    )
    return catalog


@pytest.fixture(autouse=True)
def installed_catalog(monkeypatch: pytest.MonkeyPatch) -> ArtifactCatalog:
    catalog = public_catalog()
    monkeypatch.setattr("provium.procedure.discover_catalogs", lambda: catalog)
    return catalog


def test_documented_public_api_workflow(
    tmp_path: Path, installed_catalog: ArtifactCatalog
) -> None:
    source_path = tmp_path / "source.pa"
    with Procedure("seed", "1").execute() as seed_execution:
        source_writer = TextArtifact.create(source_path)
        source_writer.write_text("hello")

    assert source_writer.closed
    assert source_writer.container_finalized

    output_path = tmp_path / "output.pa"
    with Procedure("uppercase", "1").execute() as transform_execution:
        source_reader = TextArtifact.open(source_path)
        output_writer = TextArtifact.create(output_path)
        output_writer.write_text(source_reader.read_text().upper())
        # Deliberately leave both handles open; the procedure scope owns them.

    assert source_reader.closed
    assert output_writer.closed
    assert output_writer.container_finalized

    with Procedure("verify", "1").execute():
        generic_reader = open_artifact(output_path)
        expected_reader = open_artifact(output_path, expected=TextArtifact)
        assert isinstance(generic_reader, TextReader)
        assert isinstance(expected_reader, TextReader)
        assert generic_reader.read_text() == "HELLO"
        assert expected_reader.read_text() == "HELLO"
        lineage = generic_reader.lineage

    output_header = decode_header(output_path.read_bytes())
    output_body = output_path.read_bytes()[
        output_header.body_offset : output_header.body_offset
        + output_header.body_length
    ]
    assert output_header.body_digest == hashlib.sha256(output_body).hexdigest()
    assert set(lineage.artifacts) == {source_writer.identity, output_writer.identity}
    assert set(lineage.executions) == {
        seed_execution.identity,
        transform_execution.identity,
    }
    assert (
        lineage.producing_execution(
            ArtifactReference(output_writer.identity, "example.TextV1")
        ).identity
        == transform_execution.identity
    )


def test_public_handles_reject_later_execution_context(tmp_path: Path) -> None:
    path = tmp_path / "value.pa"
    with Procedure("create", "1").execute():
        writer = TextArtifact.create(path)
        writer.write_text("value")

    with Procedure("read", "1").execute():
        reader = TextArtifact.open(path)

    with (
        Procedure("later", "1").execute(),
        pytest.raises(RuntimeError, match="context"),
    ):
        reader.body.read()


def test_discovery_function_is_part_of_public_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "provium.artifact.discovery.metadata.entry_points", lambda: FakeEntryPoints()
    )

    reset_discovery()
    assert isinstance(discover_catalogs(), ArtifactCatalog)
    reset_discovery()


class FakeEntryPoints(list[object]):
    def select(self, *, group: str) -> FakeEntryPoints:
        assert group == "provium.catalogs"
        return self
