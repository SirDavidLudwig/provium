"""Logical ownership context for artifact resources."""

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar

_active_context: ContextVar[object | None] = ContextVar(
    "provium_active_context",
    default=None,
)


def current_context() -> object | None:
    """Return the resource owner active in this logical context."""
    return _active_context.get()


@contextmanager
def activate_context(owner: object) -> Generator[None]:
    """Activate an owner temporarily and restore the prior owner afterward."""
    token = _active_context.set(owner)
    try:
        yield
    finally:
        _active_context.reset(token)


__all__ = ["activate_context", "current_context"]
