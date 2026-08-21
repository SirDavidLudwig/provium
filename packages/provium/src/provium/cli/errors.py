"""Concise, contextual diagnostics for expected CLI failures."""

from __future__ import annotations

import sys
from types import TracebackType

EXPECTED_CLI_ERRORS = (
    AttributeError,
    ImportError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)


def _origin(traceback: TracebackType | None) -> str | None:
    if traceback is None:
        return None
    while traceback.tb_next is not None:
        traceback = traceback.tb_next
    module = traceback.tb_frame.f_globals["__name__"]
    function = traceback.tb_frame.f_code.co_qualname
    return f"{module}.{function}"


def _cause(error: BaseException) -> BaseException | None:
    if error.__cause__ is not None:
        return error.__cause__
    if not error.__suppress_context__:
        return error.__context__
    return None


def _describe(error: BaseException) -> str:
    description = f"{type(error).__name__}: {error}"
    origin = _origin(error.__traceback__)
    if origin is not None:
        description += f" (raised at {origin})"
    return description


def print_cli_error(context: str, error: BaseException) -> int:
    """Print one operation-scoped exception chain and return a failure status."""
    print(f"error: {context} failed", file=sys.stderr)
    print(f"  {_describe(error)}", file=sys.stderr)
    seen = {id(error)}
    current = _cause(error)
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        print(f"  caused by {_describe(current)}", file=sys.stderr)
        current = _cause(current)
    return 2


__all__ = ["EXPECTED_CLI_ERRORS", "print_cli_error"]
