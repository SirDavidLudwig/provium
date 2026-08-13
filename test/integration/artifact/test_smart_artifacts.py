from __future__ import annotations

import struct
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from provium import Artifact, ArtifactCatalog, ArtifactReader, ArtifactWriter, Procedure


class StreamingReader(ArtifactReader):
    def records(self) -> Iterator[bytes]:
        while self.body.tell() < self.body.length:
            size = struct.unpack(">I", self.body.read(4))[0]
            yield self.body.read(size)


class StreamingWriter(ArtifactWriter):
    def append(self, value: bytes) -> None:
        self.body.write(struct.pack(">I", len(value)))
        self.body.write(value)


class StreamingArtifact(Artifact[StreamingReader, StreamingWriter]):
    reader = StreamingReader
    writer = StreamingWriter


class IndexedReader(ArtifactReader):
    def get(self, index: int) -> bytes:
        self.body.seek(0)
        index_offset = struct.unpack(">Q", self.body.read(8))[0]
        self.body.seek(index_offset + index * 8)
        record_offset = struct.unpack(">Q", self.body.read(8))[0]
        self.body.seek(record_offset)
        size = struct.unpack(">I", self.body.read(4))[0]
        return self.body.read(size)


class IndexedWriter(ArtifactWriter):
    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self.offsets: list[int] = []
        self.body.write(bytes(8))

    def append(self, value: bytes) -> None:
        self.offsets.append(self.body.tell())
        self.body.write(struct.pack(">I", len(value)))
        self.body.write(value)

    def finish_index(self) -> None:
        index_offset = self.body.tell()
        for offset in self.offsets:
            self.body.write(struct.pack(">Q", offset))
        self.body.seek(0)
        self.body.write(struct.pack(">Q", index_offset))


class IndexedArtifact(Artifact[IndexedReader, IndexedWriter]):
    reader = IndexedReader
    writer = IndexedWriter


@pytest.fixture
def smart_catalog(monkeypatch: pytest.MonkeyPatch) -> ArtifactCatalog:
    catalog = ArtifactCatalog()
    catalog.register("example.StreamingV1", StreamingArtifact)
    catalog.register("example.IndexedV1", IndexedArtifact)
    monkeypatch.setattr("provium.procedure.discover_catalogs", lambda: catalog)
    return catalog


def test_streams_records_incrementally_and_processes_large_body(
    tmp_path: Path,
    smart_catalog: ArtifactCatalog,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "streaming.pa"
    records = [f"record-{index:05d}".encode() * 8 for index in range(10_000)]
    with Procedure("write", "1").execute():
        writer = StreamingArtifact.create(path)
        for record in records:
            writer.append(record)

    def forbid_read_bytes(self: Path) -> bytes:
        raise AssertionError(
            "opening must not load the complete file with Path.read_bytes"
        )

    monkeypatch.setattr(Path, "read_bytes", forbid_read_bytes)
    with Procedure("read", "1").execute():
        reader = StreamingArtifact.open(path)
        assert list(reader.records()) == records


def test_indexed_writer_backpatches_and_reader_seeks_directly_to_subset(
    tmp_path: Path, smart_catalog: ArtifactCatalog
) -> None:
    path = tmp_path / "indexed.pa"
    records = [f"value-{index}".encode() for index in range(100)]
    with Procedure("write", "1").execute():
        writer = IndexedArtifact.create(path)
        for record in records:
            writer.append(record)
        writer.finish_index()

    with Procedure("read", "1").execute():
        reader = IndexedArtifact.open(path)
        assert reader.get(73) == records[73]
        assert reader.get(2) == records[2]
        assert reader.body.tell() < reader.body.length


def test_reader_and_writer_provider_modules_load_lazily_and_cache_independently(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reader_module = "test.support.integration.lazy_reader"
    writer_module = "test.support.integration.lazy_writer"
    sys.modules.pop(reader_module, None)
    sys.modules.pop(writer_module, None)
    from test.support.integration.lazy_artifact import LazyArtifact

    LazyArtifact._reader_type_cache = None
    LazyArtifact._writer_type_cache = None
    catalog = ArtifactCatalog()
    catalog.register("example.LazyV1", LazyArtifact)
    monkeypatch.setattr("provium.procedure.discover_catalogs", lambda: catalog)

    assert reader_module not in sys.modules
    assert writer_module not in sys.modules
    path = tmp_path / "lazy.pa"
    with Procedure("write", "1").execute():
        writer = LazyArtifact.create(path)
        writer.write(b"lazy")
    assert writer_module in sys.modules
    assert reader_module not in sys.modules

    writer_type = LazyArtifact._resolve_writer()
    with Procedure("read", "1").execute():
        reader = LazyArtifact.open(path)
        assert reader.read() == b"lazy"
    assert reader_module in sys.modules
    assert LazyArtifact._resolve_writer() is writer_type
    assert LazyArtifact._resolve_reader() is type(reader)
