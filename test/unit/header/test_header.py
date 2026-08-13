from __future__ import annotations

import json
import struct

import pytest

from provium import (
    ArtifactHeader,
    ArtifactLineage,
    ArtifactRecord,
    ArtifactReference,
    ProcedureExecutionRecord,
    ProcedureRecord,
    decode_header,
    encode_header,
)
from provium.artifact.header import CONTAINER_VERSION, MAGIC, PREFIX_SIZE


def lineage() -> ArtifactLineage:
    reference = ArtifactReference("artifact-1", "example.IntegerV1")
    execution = ProcedureExecutionRecord(
        "execution-1",
        ProcedureRecord("create", "1"),
        outputs=(reference,),
    )
    return ArtifactLineage.for_execution(
        execution,
        (ArtifactRecord(reference, "a" * 64, execution.identity),),
    )


def header(**changes: object) -> ArtifactHeader:
    values: dict[str, object] = {
        "artifact_identifier": "example.IntegerV1",
        "artifact_identity": "artifact-1",
        "body_offset": 4096,
        "body_length": 128,
        "body_digest": "a" * 64,
        "lineage": lineage(),
    }
    values.update(changes)
    return ArtifactHeader(**values)  # type: ignore[arg-type]


def test_encode_and_decode_valid_header_round_trips_every_field() -> None:
    expected = header()

    encoded = encode_header(expected)
    actual = decode_header(encoded)

    assert actual == expected
    assert actual.artifact_identifier == "example.IntegerV1"
    assert actual.artifact_identity == "artifact-1"
    assert actual.metadata_offset == PREFIX_SIZE
    assert actual.metadata_length == len(encoded) - PREFIX_SIZE
    assert actual.body_offset == 4096
    assert actual.body_length == 128
    assert actual.body_digest == "a" * 64
    assert actual.lineage == lineage()


def test_metadata_encoding_is_deterministic() -> None:
    first = header()
    second = header()

    assert encode_header(first) == encode_header(second)

    metadata = encode_header(first)[PREFIX_SIZE:]
    assert (
        metadata
        == json.dumps(
            json.loads(metadata),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
    )


def test_zero_length_body_is_supported() -> None:
    expected = header(
        body_offset=PREFIX_SIZE + 1000, body_length=0, body_digest="e3b0c442"
    )

    assert decode_header(encode_header(expected)) == expected


def test_large_offsets_and_lengths_are_supported() -> None:
    expected = header(body_offset=2**48 + 123, body_length=2**40 + 456)

    assert decode_header(encode_header(expected)) == expected


def test_non_default_metadata_location_is_preserved() -> None:
    expected = header(metadata_offset=PREFIX_SIZE + 32)
    encoded = encode_header(expected)

    assert encoded[PREFIX_SIZE : expected.metadata_offset] == bytes(32)
    assert decode_header(encoded) == expected


def test_rejects_invalid_magic_bytes() -> None:
    encoded = bytearray(encode_header(header()))
    encoded[: len(MAGIC)] = b"BADMAGIC"

    with pytest.raises(ValueError, match="magic"):
        decode_header(encoded)


def test_rejects_unsupported_container_version() -> None:
    encoded = bytearray(encode_header(header()))
    struct.pack_into(">H", encoded, len(MAGIC), CONTAINER_VERSION + 1)

    with pytest.raises(ValueError, match="version"):
        decode_header(encoded)


@pytest.mark.parametrize("length", [0, 1, PREFIX_SIZE - 1])
def test_rejects_truncated_fixed_header(length: int) -> None:
    with pytest.raises(ValueError, match="fixed header"):
        decode_header(encode_header(header())[:length])


def test_rejects_truncated_metadata() -> None:
    encoded = encode_header(header())

    with pytest.raises(ValueError, match="truncated metadata"):
        decode_header(encoded[:-1])


@pytest.mark.parametrize("metadata", [b"not-json", b"[]", b'{"body_offset":1}'])
def test_rejects_malformed_metadata(metadata: bytes) -> None:
    prefix = struct.pack(">8sHQQ", MAGIC, CONTAINER_VERSION, PREFIX_SIZE, len(metadata))

    with pytest.raises(ValueError, match="metadata"):
        decode_header(prefix + metadata)


def test_rejects_metadata_offset_inside_fixed_header() -> None:
    encoded = bytearray(encode_header(header()))
    struct.pack_into(">Q", encoded, len(MAGIC) + 2, PREFIX_SIZE - 1)

    with pytest.raises(ValueError, match="metadata offset"):
        decode_header(encoded)


def test_rejects_noncanonical_metadata_encoding() -> None:
    encoded = encode_header(header())
    metadata = encoded[PREFIX_SIZE:] + b" "
    prefix = struct.pack(">8sHQQ", MAGIC, CONTAINER_VERSION, PREFIX_SIZE, len(metadata))

    with pytest.raises(ValueError, match="metadata encoding"):
        decode_header(prefix + metadata)


def test_encode_requires_an_artifact_header() -> None:
    with pytest.raises(TypeError, match="ArtifactHeader"):
        encode_header(object())  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"artifact_identifier": ""}, "artifact_identifier"),
        ({"artifact_identity": ""}, "artifact_identity"),
        ({"body_offset": -1}, "body_offset"),
        ({"body_length": -1}, "body_length"),
        ({"body_digest": ""}, "body_digest"),
        ({"lineage": object()}, "lineage"),
        ({"metadata_offset": PREFIX_SIZE - 1}, "metadata_offset"),
    ],
)
def test_header_validates_fields(changes: dict[str, object], message: str) -> None:
    with pytest.raises((TypeError, ValueError), match=message):
        header(**changes)
