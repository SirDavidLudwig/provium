"""Logical execution-context state shared by context-bound resources."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar, Token

_active_context: ContextVar[object | None] = ContextVar(
    "provium_active_execution_context",
    default=None,
)


def current_context() -> object | None:
    """Return the active execution-context owner in this logical context."""
    return _active_context.get()


def set_context(owner: object) -> Token[object | None]:
    """Set the active owner and return the token required to restore it."""
    return _active_context.set(owner)


def reset_context(token: Token[object | None]) -> None:
    """Restore the logical context represented by a prior token."""
    _active_context.reset(token)


@contextmanager
def activate_context(owner: object) -> Generator[None]:
    """Activate an owner temporarily, restoring the previous owner on exit."""
    token = set_context(owner)
    try:
        yield
    finally:
        reset_context(token)


__all__ = ["activate_context", "current_context", "reset_context", "set_context"]
