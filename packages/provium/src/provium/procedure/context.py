"""Contexts and cooperative cancellation for procedure lifecycle hooks."""

from pathlib import Path
from tempfile import gettempdir
from threading import Event


class ProcedureCancelledError(RuntimeError):
    """Raised when a procedure invocation observes cancellation."""


class CancellationToken:
    """A thread-safe cooperative cancellation signal."""

    __slots__ = ("_event",)

    def __init__(self) -> None:
        self._event = Event()

    @property
    def cancelled(self) -> bool:
        """Return whether cancellation has been requested."""
        return self._event.is_set()

    def cancel(self) -> None:
        """Request cancellation; repeated requests have no additional effect."""
        self._event.set()

    def raise_if_cancelled(self) -> None:
        """Raise when cancellation has been requested."""
        if self.cancelled:
            raise ProcedureCancelledError("procedure execution was cancelled")


class _ProcedureContext:
    __slots__ = ("_cancellation", "_temporary_directory")

    def __init__(
        self,
        cancellation: CancellationToken | None = None,
        temporary_directory: Path | None = None,
    ) -> None:
        self._cancellation = cancellation or CancellationToken()
        self._temporary_directory = (
            Path(gettempdir())
            if temporary_directory is None
            else Path(temporary_directory)
        )

    @property
    def cancellation(self) -> CancellationToken:
        """Return the cooperative cancellation signal for this lifecycle call."""
        return self._cancellation

    @property
    def temporary_directory(self) -> Path:
        """Return the directory reserved for temporary lifecycle data."""
        return self._temporary_directory


class ProcedureSetupContext(_ProcedureContext):
    """Context supplied while a procedure prepares reusable state."""


class ProcedureProcessContext(_ProcedureContext):
    """Context supplied while a procedure processes one invocation."""


__all__ = [
    "CancellationToken",
    "ProcedureCancelledError",
    "ProcedureProcessContext",
    "ProcedureSetupContext",
]
