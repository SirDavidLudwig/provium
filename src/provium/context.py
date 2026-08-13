"""Logical execution-context state shared by context-bound resources."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar, Token

_active_context: ContextVar[object | None] = ContextVar(
    "provium_active_session",
    default=None,
)

_active_execution: ContextVar[object | None] = ContextVar(
    "provium_active_execution",
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


def current_execution_context() -> object | None:
    """Return the active procedure execution in this logical context."""
    return _active_execution.get()


def set_execution_context(owner: object) -> Token[object | None]:
    return _active_execution.set(owner)


def reset_execution_context(token: Token[object | None]) -> None:
    _active_execution.reset(token)


@contextmanager
def activate_context(owner: object) -> Generator[None]:
    """Activate an owner temporarily, restoring the previous owner on exit."""
    token = set_context(owner)
    try:
        yield
    finally:
        reset_context(token)


__all__ = [
    "activate_context",
    "current_context",
    "current_execution_context",
    "reset_context",
    "reset_execution_context",
    "set_context",
    "set_execution_context",
]
