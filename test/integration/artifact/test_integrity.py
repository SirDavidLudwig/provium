from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest

from provium import (
    Artifact,
    ArtifactCatalog,
    ArtifactHeader,
    ArtifactReader,
    ArtifactWriter,
    Procedure,
    decode_header,
    encode_header,
)
from provium.artifact.header import CONTAINER_VERSION, MAGIC, PREFIX_SIZE


class BytesReader(ArtifactReader):
    def read(self) -> bytes:
        return self.body.read()


class BytesWriter(ArtifactWriter):
    def write(self, value: bytes) -> int:
        return self.body.write(value)


BytesArtifact = Artifact("Bytes", reader=BytesReader, writer=BytesWriter)


@pytest.fixture(autouse=True)
def discovered_catalog(monkeypatch: pytest.MonkeyPatch) -> ArtifactCatalog:
    catalog = ArtifactCatalog()
    catalog.register("example.BytesV1", BytesArtifact)
    monkeypatch.setattr("provium.procedure.discover_catalogs", lambda: catalog)
    return catalog


def create_valid(path: Path, body: bytes = b"payload") -> ArtifactHeader:
    with Procedure("create", "1").execute():
        writer = BytesArtifact.create(path)
        writer.write(body)
    return decode_header(path.read_bytes())


def replace_metadata(path: Path, update: dict[str, object]) -> None:
    data = path.read_bytes()
    _, _, metadata_offset, metadata_length = struct.unpack_from(">8sHQQ", data)
    metadata = json.loads(
        data[metadata_offset : metadata_offset + metadata_length].decode()
    )
    metadata.update(update)
    encoded = json.dumps(metadata, sort_keys=True, separators=(",", ":")).encode()
    prefix = struct.pack(
        ">8sHQQ", MAGIC, CONTAINER_VERSION, metadata_offset, len(encoded)
    )
    path.write_bytes(prefix + data[PREFIX_SIZE:metadata_offset] + encoded)


def test_valid_artifact_and_untouched_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "valid.pa"
    expected_header = create_valid(path, b"complete")

    with Procedure("read", "1").execute():
        reader = BytesArtifact.open(path)
        assert reader.read() == b"complete"
        assert reader.metadata == expected_header


def test_detects_modified_body_bytes(tmp_path: Path) -> None:
    path = tmp_path / "modified.pa"
    create_valid(path)
    data = bytearray(path.read_bytes())
    data[-1] ^= 1
    path.write_bytes(data)

    with Procedure("read", "1").execute(), pytest.raises(ValueError, match="digest"):
        BytesArtifact.open(path)


def test_detects_truncated_body_bytes(tmp_path: Path) -> None:
    path = tmp_path / "truncated.pa"
    create_valid(path)
    path.write_bytes(path.read_bytes()[:-1])

    with Procedure("read", "1").execute(), pytest.raises(ValueError, match="truncated"):
        BytesArtifact.open(path)


def test_detects_body_offset_overlapping_header(tmp_path: Path) -> None:
    path = tmp_path / "offset.pa"
    original = create_valid(path)
    invalid = ArtifactHeader(
        artifact_identifier=original.artifact_identifier,
        artifact_identity=original.artifact_identity,
        body_offset=PREFIX_SIZE,
        body_length=original.body_length,
        body_digest=original.body_digest,
        lineage=original.lineage,
    )
    body = path.read_bytes()[
        original.body_offset : original.body_offset + original.body_length
    ]
    encoded = encode_header(invalid)
    path.write_bytes(encoded + body)

    with (
        Procedure("read", "1").execute(),
        pytest.raises(ValueError, match="body offset"),
    ):
        BytesArtifact.open(path)


def test_detects_invalid_negative_body_length(tmp_path: Path) -> None:
    path = tmp_path / "length.pa"
    create_valid(path)
    replace_metadata(path, {"body_length": -1})

    with Procedure("read", "1").execute(), pytest.raises(ValueError, match="metadata"):
        BytesArtifact.open(path)


def test_detects_body_extending_past_eof(tmp_path: Path) -> None:
    path = tmp_path / "past-eof.pa"
    header = create_valid(path)
    replace_metadata(path, {"body_length": header.body_length + 10_000})

    with Procedure("read", "1").execute(), pytest.raises(ValueError, match="truncated"):
        BytesArtifact.open(path)


def test_detects_malformed_metadata(tmp_path: Path) -> None:
    path = tmp_path / "metadata.pa"
    create_valid(path)
    data = path.read_bytes()
    malformed = b"not-json"
    prefix = struct.pack(
        ">8sHQQ", MAGIC, CONTAINER_VERSION, PREFIX_SIZE, len(malformed)
    )
    path.write_bytes(prefix + malformed + data[PREFIX_SIZE + len(malformed) :])

    with Procedure("read", "1").execute(), pytest.raises(ValueError, match="metadata"):
        BytesArtifact.open(path)


def test_detects_truncated_fixed_prefix_while_opening(tmp_path: Path) -> None:
    path = tmp_path / "fixed-header.pa"
    path.write_bytes(MAGIC)

    with (
        Procedure("read", "1").execute(),
        pytest.raises(ValueError, match="fixed header"),
    ):
        BytesArtifact.open(path)


@pytest.mark.parametrize(
    ("offset", "value", "message"),
    [
        (0, b"BADMAGIC", "magic"),
        (len(MAGIC), struct.pack(">H", CONTAINER_VERSION + 1), "version"),
    ],
)
def test_detects_invalid_prefix(
    tmp_path: Path, offset: int, value: bytes, message: str
) -> None:
    path = tmp_path / "prefix.pa"
    create_valid(path)
    data = bytearray(path.read_bytes())
    data[offset : offset + len(value)] = value
    path.write_bytes(data)

    with Procedure("read", "1").execute(), pytest.raises(ValueError, match=message):
        BytesArtifact.open(path)


def test_detects_corruption_after_seek_and_backpatch(tmp_path: Path) -> None:
    path = tmp_path / "backpatch.pa"
    with Procedure("create", "1").execute():
        writer = BytesArtifact.create(path)
        writer.write(b"0000payload")
        writer.body.seek(0)
        writer.write(b"0011")

    header = decode_header(path.read_bytes())
    data = bytearray(path.read_bytes())
    data[header.body_offset + 1] ^= 1
    path.write_bytes(data)

    with Procedure("read", "1").execute(), pytest.raises(ValueError, match="digest"):
        BytesArtifact.open(path)
