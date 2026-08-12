"""Context-bound, body-relative binary stream regions."""

from __future__ import annotations

import io
import os
from typing import BinaryIO

from .context import current_context


class BodyRegion:
    """Expose a binary stream body using logical body-relative positions."""

    def __init__(
        self,
        stream: BinaryIO,
        body_offset: int,
        body_length: int,
        owner: object,
        *,
        writable: bool = False,
    ) -> None:
        if body_offset < 0 or body_length < 0:
            raise ValueError("body boundaries must be non-negative")
        self._stream = stream
        self._body_offset = body_offset
        self._length = body_length
        self._owner = owner
        self._writable = writable
        self._position = 0
        self._closed = False

    @property
    def length(self) -> int:
        return self._length

    @property
    def closed(self) -> bool:
        return self._closed

    def check_context(self) -> None:
        if current_context() is not self._owner:
            raise RuntimeError(
                "body region is not owned by the active execution context"
            )
        if not getattr(self._owner, "active", False):
            raise RuntimeError("body region owner is no longer active")

    def check_access(self) -> None:
        self.check_context()
        if self._closed:
            raise ValueError("body region is closed")

    def close(self) -> None:
        if self._closed:
            return
        self.check_context()
        self._closed = True

    def _position_stream(self) -> None:
        self._stream.seek(self._body_offset + self._position, os.SEEK_SET)

    def tell(self) -> int:
        self.check_access()
        return self._position

    def seek(self, offset: int, whence: int = os.SEEK_SET) -> int:
        self.check_access()
        if whence == os.SEEK_SET:
            position = offset
        elif whence == os.SEEK_CUR:
            position = self._position + offset
        elif whence == os.SEEK_END:
            position = self._length + offset
        else:
            raise ValueError("invalid seek whence")
        if position < 0:
            raise ValueError("cannot seek before the artifact body")
        if not self._writable and position > self._length:
            raise ValueError("cannot seek beyond the finalized artifact body")
        self._position = position
        self._position_stream()
        return position

    def read(self, size: int | None = -1) -> bytes:
        self.check_access()
        if self._writable:
            raise io.UnsupportedOperation("read")
        remaining = self._length - self._position
        read_size = remaining if size is None or size < 0 else min(size, remaining)
        self._position_stream()
        result = self._stream.read(read_size)
        self._position += len(result)
        return result

    def readinto(self, buffer: bytearray | memoryview) -> int:
        self.check_access()
        if self._writable:
            raise io.UnsupportedOperation("read")
        target = memoryview(buffer).cast("B")
        result = self.read(len(target))
        target[: len(result)] = result
        return len(result)

    def write(self, data: bytes | bytearray | memoryview) -> int:
        self.check_access()
        if not self._writable:
            raise io.UnsupportedOperation("write")
        self._position_stream()
        written = self._stream.write(data)
        self._position += written
        self._length = max(self._length, self._position)
        return written

    def flush(self) -> None:
        self.check_access()
        self._stream.flush()


__all__ = ["BodyRegion"]
