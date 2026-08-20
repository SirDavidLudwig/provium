"""Nested ownership scopes for artifact resources."""

from __future__ import annotations

from contextlib import AbstractContextManager
from types import TracebackType
from typing import Protocol, Self

from .context import activate_context, current_context


class _Closeable(Protocol):
    def close(self) -> None: ...


class Session:
    """Own resources within a single-use, nestable logical context."""

    def __init__(self) -> None:
        self.active = False
        self.parent: Session | None = None
        self._used = False
        self._activation: AbstractContextManager[None] | None = None
        self._managed_resources: list[_Closeable] = []

    def __enter__(self) -> Self:
        if self._used:
            raise RuntimeError("session has already been entered")
        parent = current_context()
        if parent is not None and not isinstance(parent, Session):
            raise RuntimeError("active artifact context is not a session")
        self._used = True
        self.parent = parent
        self.active = True
        activation = activate_context(self)
        activation.__enter__()
        self._activation = activation
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if not self.active or current_context() is not self or self._activation is None:
            raise RuntimeError("session is not active")
        activation = self._activation
        close_error: Exception | None = None
        try:
            close_error = self._close_resources()
        finally:
            self.active = False
            self._activation = None
            activation.__exit__(exc_type, exc_value, traceback)
        if exc_type is None and close_error is not None:
            raise close_error

    def _manage(self, resource: _Closeable) -> None:
        """Register a resource to close when this session exits."""
        if not self.active or current_context() is not self:
            raise RuntimeError("managed resources require the active session")
        if not callable(getattr(resource, "close", None)):
            raise TypeError("managed resource must provide a callable close operation")
        self._managed_resources.append(resource)

    def _owns_active_context(self) -> bool:
        """Return whether this session owns the current nested session."""
        current = current_context()
        while isinstance(current, Session):
            if current is self:
                return self.active
            current = current.parent
        return False

    def _close_resources(self) -> Exception | None:
        first_error: Exception | None = None
        for resource in reversed(self._managed_resources):
            try:
                resource.close()
            except Exception as error:  # noqa: BLE001
                if first_error is None:
                    first_error = error
        return first_error


def session() -> Session:
    """Create a new artifact resource session."""
    return Session()


def current_session() -> Session | None:
    """Return the active session, if any."""
    current = current_context()
    return current if isinstance(current, Session) else None


__all__ = ["Session", "current_session", "session"]
