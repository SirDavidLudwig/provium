"""Private exact-binding authorization for procedure callbacks."""

from __future__ import annotations

from collections.abc import Generator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from provium.artifact import ArtifactWriteBinding, ArtifactWriter


_ACTIVE_OUTPUTS: ContextVar[Mapping[int, ArtifactWriter] | None] = ContextVar(
    "provium_procedure_outputs",
    default=None,
)


@contextmanager
def authorize_outputs(
    bindings: Mapping[str, ArtifactWriteBinding[Any]],
    writers: Mapping[str, ArtifactWriter],
) -> Generator[None]:
    """Authorize the exact declared bindings for one callback activation."""
    authorized = {id(bindings[name]): writers[name] for name in bindings}
    token = _ACTIVE_OUTPUTS.set(authorized)
    try:
        yield
    finally:
        _ACTIVE_OUTPUTS.reset(token)


def open_authorized_output[WriterT: ArtifactWriter](
    binding: ArtifactWriteBinding[WriterT],
) -> WriterT:
    """Return the staged writer authorized for an exact binding object."""
    active = _ACTIVE_OUTPUTS.get()
    if active is None:
        raise RuntimeError(
            "artifact write binding requires an active procedure callback"
        )
    writer = active.get(id(binding))
    if writer is None:
        raise RuntimeError(
            "artifact write binding was not declared for the active procedure callback"
        )
    return cast(WriterT, writer)


__all__: list[str] = []
