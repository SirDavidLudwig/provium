"""Tests for context-owned artifact body regions."""

from __future__ import annotations

import io
import os
from dataclasses import dataclass

import pytest

from provium.artifact.region import BodyRegion
from provium.context import activate_context, current_context


@dataclass
class Owner:
    active: bool = True


def test_context_activation_is_nested_and_restored() -> None:
    outer = Owner()
    inner = Owner()

    assert current_context() is None
    with activate_context(outer):
        assert current_context() is outer
        with activate_context(inner):
            assert current_context() is inner
        assert current_context() is outer
    assert current_context() is None


def test_readable_region_uses_bounded_body_relative_positions() -> None:
    owner = Owner()
    stream = io.BytesIO(b"prefix" + b"abcdefghij" + b"trailing")
    region = BodyRegion(stream, 6, 10, owner)
    target = bytearray(3)

    with activate_context(owner):
        assert region.tell() == 0
        assert region.read(2) == b"ab"
        assert region.readinto(target) == 3
        assert target == b"cde"
        assert region.seek(1, os.SEEK_CUR) == 6
        assert region.seek(-2, os.SEEK_END) == 8
        assert region.read() == b"ij"
        assert region.read() == b""
        assert region.tell() == 10

    assert stream.tell() == 16


def test_writable_region_supports_backpatching_and_tracks_extent() -> None:
    owner = Owner()
    stream = io.BytesIO(b"prefix")
    region = BodyRegion(stream, 6, 0, owner, writable=True)

    with activate_context(owner):
        assert region.write(b"0000payload") == 11
        assert region.seek(0) == 0
        assert region.write(memoryview(b"0011")) == 4
        assert region.seek(2, os.SEEK_END) == 13
        assert region.write(b"!") == 1
        region.flush()

    assert region.length == 14
    assert stream.getvalue() == b"prefix0011payload\x00\x00!"


def test_region_enforces_mode_seek_and_ownership_boundaries() -> None:
    owner = Owner()
    reader = BodyRegion(io.BytesIO(b"body"), 0, 4, owner)
    writer = BodyRegion(io.BytesIO(), 0, 0, owner, writable=True)

    with pytest.raises(RuntimeError, match="active context"):
        reader.tell()

    with activate_context(owner):
        with pytest.raises(io.UnsupportedOperation, match="write"):
            reader.write(b"value")
        with pytest.raises(io.UnsupportedOperation, match="read"):
            writer.read()
        with pytest.raises(io.UnsupportedOperation, match="read"):
            writer.readinto(bytearray(1))
        with pytest.raises(ValueError, match="before"):
            reader.seek(-1)
        with pytest.raises(ValueError, match="beyond"):
            reader.seek(5)
        with pytest.raises(ValueError, match="whence"):
            reader.seek(0, 999)

    owner.active = False
    with activate_context(owner), pytest.raises(RuntimeError, match="no longer active"):
        reader.tell()


def test_region_accepts_an_owner_authorized_nested_context() -> None:
    class NestedOwner:
        active = True

        def _owns_active_context(self) -> bool:
            return True

    owner = NestedOwner()
    region = BodyRegion(io.BytesIO(b"body"), 0, 4, owner)

    with activate_context(Owner()):
        assert region.read() == b"body"


def test_close_is_idempotent_and_can_own_the_underlying_stream() -> None:
    owner = Owner()
    stream = io.BytesIO(b"body")
    region = BodyRegion(stream, 0, 4, owner, close_stream=True)

    with activate_context(owner):
        region.close()
        region.close()
        assert region.closed
        with pytest.raises(ValueError, match="closed"):
            region.read()

    assert stream.closed

    retained_stream = io.BytesIO(b"body")
    retained_region = BodyRegion(retained_stream, 0, 4, owner)
    with activate_context(owner):
        retained_region.close()
    assert not retained_stream.closed


@pytest.mark.parametrize("offset,length", [(-1, 0), (0, -1)])
def test_region_rejects_negative_boundaries(offset: int, length: int) -> None:
    with pytest.raises(ValueError, match="non-negative"):
        BodyRegion(io.BytesIO(), offset, length, Owner())
