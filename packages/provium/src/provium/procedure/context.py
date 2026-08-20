"""Contexts supplied to procedure lifecycle hooks."""


class ProcedureSetupContext:
    """Context supplied while a procedure prepares reusable state."""

    __slots__ = ()


class ProcedureProcessContext:
    """Context supplied while a procedure processes one invocation."""

    __slots__ = ()


__all__ = ["ProcedureProcessContext", "ProcedureSetupContext"]
