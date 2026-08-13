from __future__ import annotations

import io
import os
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import pytest

from provium.artifact.region import BodyRegion
from provium.context import activate_context


@dataclass
class Owner:
    active: bool = True


@contextmanager
def active(owner: Owner) -> Generator[None]:
    with activate_context(owner):
        yield


def readable(
    body: bytes = b"abcdefghij",
    *,
    prefix: bytes = b"metadata",
    owner: Owner | None = None,
) -> tuple[BodyRegion, io.BytesIO, Owner]:
    context_owner = owner or Owner()
    stream = io.BytesIO(prefix + body + b"trailing")
    region = BodyRegion(
        stream,
        body_offset=len(prefix),
        body_length=len(body),
        owner=context_owner,
    )
    return region, stream, context_owner


def writable(
    *, prefix: bytes = b"metadata", owner: Owner | None = None
) -> tuple[BodyRegion, io.BytesIO, Owner]:
    context_owner = owner or Owner()
    stream = io.BytesIO(prefix)
    region = BodyRegion(
        stream,
        body_offset=len(prefix),
        body_length=0,
        owner=context_owner,
        writable=True,
    )
    return region, stream, context_owner


def test_logical_zero_maps_to_physical_body_start_and_reads_complete_body() -> None:
    region, stream, owner = readable()

    with active(owner):
        assert region.tell() == 0
        assert region.read() == b"abcdefghij"
        assert region.tell() == 10
        assert stream.tell() == len(b"metadata") + 10


def test_reads_partial_ranges_and_readinto() -> None:
    region, _, owner = readable()
    target = bytearray(4)

    with active(owner):
        assert region.read(3) == b"abc"
        assert region.readinto(target) == 4
        assert target == b"defg"
        assert region.read(100) == b"hij"
        assert region.readinto(bytearray(2)) == 0


def test_seeks_from_start_current_and_end_using_body_relative_positions() -> None:
    region, _, owner = readable()

    with active(owner):
        assert region.seek(4) == 4
        assert region.seek(2, os.SEEK_CUR) == 6
        assert region.seek(-2, os.SEEK_END) == 8
        assert region.tell() == 8
        assert region.read() == b"ij"


@pytest.mark.parametrize(
    ("offset", "whence", "message"),
    [
        (-1, os.SEEK_SET, "before"),
        (-1, os.SEEK_CUR, "before"),
        (-11, os.SEEK_END, "before"),
        (11, os.SEEK_SET, "beyond"),
        (1, 999, "whence"),
    ],
)
def test_finalized_reader_rejects_invalid_seeks(
    offset: int, whence: int, message: str
) -> None:
    region, _, owner = readable()

    with active(owner), pytest.raises((ValueError, OSError), match=message):
        region.seek(offset, whence)


def test_streaming_writes_update_length_and_flush() -> None:
    region, stream, owner = writable()

    with active(owner):
        assert region.write(b"abc") == 3
        assert region.write(memoryview(b"def")) == 3
        region.flush()
        assert region.tell() == 6
        assert region.length == 6

    assert stream.getvalue() == b"metadataabcdef"


def test_random_access_writes_and_backpatching_preserve_final_extent() -> None:
    region, stream, owner = writable()

    with active(owner):
        region.write(b"0000payload")
        region.seek(0)
        region.write(b"0011")
        region.seek(2, os.SEEK_END)
        region.write(b"!")

    assert region.length == 14
    assert stream.getvalue() == b"metadata0011payload\x00\x00!"


def test_writer_cannot_seek_before_body() -> None:
    region, _, owner = writable()

    with active(owner), pytest.raises(ValueError, match="before"):
        region.seek(-1)


def test_read_only_and_write_only_operations_are_rejected() -> None:
    reader, _, reader_owner = readable()
    writer, _, writer_owner = writable()

    with active(reader_owner), pytest.raises(io.UnsupportedOperation, match="write"):
        reader.write(b"value")
    with active(writer_owner), pytest.raises(io.UnsupportedOperation, match="read"):
        writer.read()
    with active(writer_owner), pytest.raises(io.UnsupportedOperation, match="read"):
        writer.readinto(bytearray(1))


def test_filesystem_backed_region(tmp_path: Path) -> None:
    path = tmp_path / "artifact.pa"
    path.write_bytes(b"prefixbody-suffix")
    owner = Owner()

    with path.open("r+b") as stream:
        region = BodyRegion(stream, body_offset=6, body_length=4, owner=owner)
        with active(owner):
            assert region.read() == b"body"


def test_rejects_access_after_owner_ends() -> None:
    region, _, owner = readable()
    owner.active = False

    with active(owner), pytest.raises(RuntimeError, match="active"):
        region.read()


def test_rejects_access_outside_or_under_another_context() -> None:
    region, _, owner = readable()

    with pytest.raises(RuntimeError, match="context"):
        region.tell()
    with active(Owner()), pytest.raises(RuntimeError, match="context"):
        region.tell()


@pytest.mark.parametrize(
    ("body_offset", "body_length"),
    [(-1, 0), (0, -1)],
)
def test_region_rejects_negative_boundaries(body_offset: int, body_length: int) -> None:
    with pytest.raises(ValueError, match="non-negative"):
        BodyRegion(io.BytesIO(), body_offset, body_length, Owner())
