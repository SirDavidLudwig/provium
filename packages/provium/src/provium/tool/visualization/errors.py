"""Errors raised by provenance visualization backends."""


class BackendUnavailableError(RuntimeError):
    """Raised when a requested visualization backend is not installed."""


class UnsupportedFormatError(ValueError):
    """Raised when a visualization backend cannot produce a format."""
