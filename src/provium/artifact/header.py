"""Binary container prefix and deterministic artifact metadata encoding."""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass, field
from typing import Any

from ..provenance import ArtifactLineage

MAGIC = b"PROVIUM\0"
CONTAINER_VERSION = 1
_PREFIX = struct.Struct(">8sHQQ")
PREFIX_SIZE = _PREFIX.size
_METADATA_KEYS = {
    "artifact_identifier",
    "artifact_identity",
    "body_offset",
    "body_length",
    "body_digest",
    "lineage",
}


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")


def _metadata_bytes(header: ArtifactHeader) -> bytes:
    return json.dumps(
        {
            "artifact_identifier": header.artifact_identifier,
            "artifact_identity": header.artifact_identity,
            "body_digest": header.body_digest,
            "body_length": header.body_length,
            "body_offset": header.body_offset,
            "lineage": header.lineage.to_dict(),
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


@dataclass(frozen=True, slots=True)
class ArtifactHeader:
    """The generic metadata required to locate and identify an artifact body."""

    artifact_identifier: str
    artifact_identity: str
    body_offset: int
    body_length: int
    body_digest: str
    lineage: ArtifactLineage
    metadata_offset: int = PREFIX_SIZE
    metadata_length: int = field(init=False)

    def __post_init__(self) -> None:
        _require_text(self.artifact_identifier, "artifact_identifier")
        _require_text(self.artifact_identity, "artifact_identity")
        if not isinstance(self.body_offset, int) or self.body_offset < 0:
            raise ValueError("body_offset must be a non-negative integer")
        if not isinstance(self.body_length, int) or self.body_length < 0:
            raise ValueError("body_length must be a non-negative integer")
        _require_text(self.body_digest, "body_digest")
        if not isinstance(self.lineage, ArtifactLineage):
            raise TypeError("lineage must be an ArtifactLineage")
        if (
            not isinstance(self.metadata_offset, int)
            or self.metadata_offset < PREFIX_SIZE
        ):
            raise ValueError("metadata_offset must not overlap the fixed header")
        object.__setattr__(self, "metadata_length", len(_metadata_bytes(self)))


def encode_header(header: ArtifactHeader) -> bytes:
    """Encode a complete fixed prefix and its canonical metadata."""
    if not isinstance(header, ArtifactHeader):
        raise TypeError("header must be an ArtifactHeader")
    metadata = _metadata_bytes(header)
    prefix = _PREFIX.pack(
        MAGIC,
        CONTAINER_VERSION,
        header.metadata_offset,
        len(metadata),
    )
    padding = bytes(header.metadata_offset - PREFIX_SIZE)
    return prefix + padding + metadata


def _decode_metadata(metadata_bytes: bytes, metadata_offset: int) -> ArtifactHeader:
    metadata: Any = json.loads(metadata_bytes.decode("utf-8"))
    if not isinstance(metadata, dict) or set(metadata) != _METADATA_KEYS:
        raise ValueError("invalid metadata shape")
    return ArtifactHeader(
        artifact_identifier=metadata["artifact_identifier"],
        artifact_identity=metadata["artifact_identity"],
        body_offset=metadata["body_offset"],
        body_length=metadata["body_length"],
        body_digest=metadata["body_digest"],
        lineage=ArtifactLineage.from_dict(metadata["lineage"]),
        metadata_offset=metadata_offset,
    )


def decode_header(data: bytes | bytearray | memoryview) -> ArtifactHeader:
    """Decode and validate a complete artifact header from bytes."""
    if len(data) < PREFIX_SIZE:
        raise ValueError("truncated fixed header")
    magic, version, metadata_offset, metadata_length = _PREFIX.unpack_from(data)
    if magic != MAGIC:
        raise ValueError("invalid artifact magic bytes")
    if version != CONTAINER_VERSION:
        raise ValueError(f"unsupported container version: {version}")
    if metadata_offset < PREFIX_SIZE:
        raise ValueError("metadata offset overlaps the fixed header")
    metadata_end = metadata_offset + metadata_length
    if len(data) < metadata_end:
        raise ValueError("truncated metadata")
    metadata_bytes = bytes(data[metadata_offset:metadata_end])
    try:
        header = _decode_metadata(metadata_bytes, metadata_offset)
    except (
        KeyError,
        TypeError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValueError,
    ) as error:
        raise ValueError("malformed artifact metadata") from error
    if (
        metadata_offset != header.metadata_offset
        or metadata_length != header.metadata_length
    ):
        raise ValueError("malformed artifact metadata encoding")
    return header


__all__ = [
    "CONTAINER_VERSION",
    "MAGIC",
    "PREFIX_SIZE",
    "ArtifactHeader",
    "decode_header",
    "encode_header",
]
