from __future__ import annotations

from pathlib import Path

import pytest

from provium import (
    Artifact,
    ArtifactCatalog,
    ArtifactReader,
    ArtifactWriter,
    Procedure,
    current_execution,
)


class BytesReader(ArtifactReader):
    def read(self) -> bytes:
        return self.body.read()


class BytesWriter(ArtifactWriter):
    def write(self, value: bytes) -> int:
        return self.body.write(value)


class BytesArtifact(Artifact[BytesReader, BytesWriter]):
    reader = BytesReader
    writer = BytesWriter


@pytest.fixture(autouse=True)
def discovered_catalog(monkeypatch: pytest.MonkeyPatch) -> ArtifactCatalog:
    catalog = ArtifactCatalog()
    catalog.register("example.BytesV1", BytesArtifact)
    monkeypatch.setattr("provium.procedure.discover_catalogs", lambda: catalog)
    return catalog


def create_valid(path: Path, body: bytes = b"source") -> None:
    with Procedure("seed", "1").execute():
        writer = BytesArtifact.create(path)
        writer.write(body)


def test_exception_closes_readers_and_writers_and_invalidates_handles(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.pa"
    output = tmp_path / "failed.pa"
    create_valid(source)

    with pytest.raises(LookupError, match="procedure failed"):
        with Procedure("fail", "1").execute():
            reader = BytesArtifact.open(source)
            writer = BytesArtifact.create(output)
            writer.write(reader.read())
            raise LookupError("procedure failed")

    assert reader.closed
    assert writer.closed
    assert not writer.container_finalized
    assert current_execution() is None
    with pytest.raises(RuntimeError, match="context"):
        reader.body
    with pytest.raises(RuntimeError, match="context"):
        writer.body


def test_failed_output_is_not_a_valid_artifact(tmp_path: Path) -> None:
    output = tmp_path / "failed.pa"

    with pytest.raises(RuntimeError, match="failure"):
        with Procedure("fail", "1").execute():
            writer = BytesArtifact.create(output)
            writer.write(b"incomplete")
            raise RuntimeError("failure")

    assert not output.exists()


def test_failure_cleanup_handles_multiple_open_artifacts(tmp_path: Path) -> None:
    source = tmp_path / "source.pa"
    create_valid(source)

    with pytest.raises(RuntimeError, match="failure"):
        with Procedure("fail", "1").execute():
            first_reader = BytesArtifact.open(source)
            second_reader = BytesArtifact.open(source)
            first_writer = BytesArtifact.create(tmp_path / "first.pa")
            second_writer = BytesArtifact.create(tmp_path / "second.pa")
            raise RuntimeError("failure")

    assert all(
        resource.closed
        for resource in (first_reader, second_reader, first_writer, second_writer)
    )
    assert not (tmp_path / "first.pa").exists()
    assert not (tmp_path / "second.pa").exists()


def test_cleanup_continues_and_preserves_original_exception_when_close_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.pa"
    create_valid(source)
    original_error = LookupError("original failure")

    with pytest.raises(LookupError) as caught:
        with Procedure("fail", "1").execute():
            broken_reader = BytesArtifact.open(source)
            healthy_reader = BytesArtifact.open(source)
            writer = BytesArtifact.create(tmp_path / "failed.pa")

            def broken_close() -> None:
                raise OSError("cleanup failure")

            monkeypatch.setattr(broken_reader, "close", broken_close)
            monkeypatch.setattr(broken_reader._body, "close", broken_close)
            raise original_error

    assert caught.value is original_error
    assert healthy_reader.closed
    assert writer.closed
    assert current_execution() is None


def test_failure_restores_context_for_later_execution(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError):
        with Procedure("fail", "1").execute():
            raise RuntimeError("failure")

    with Procedure("later", "1").execute() as later:
        assert current_execution() is later


def test_failure_cleanup_tolerates_writer_close_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(RuntimeError, match="original failure"):
        with Procedure("fail", "1").execute():
            writer = BytesArtifact.create(tmp_path / "failed.pa")

            def broken_close() -> None:
                raise OSError("cleanup failure")

            monkeypatch.setattr(writer, "close", broken_close)
            monkeypatch.setattr(writer._body, "close", broken_close)
            raise RuntimeError("original failure")
