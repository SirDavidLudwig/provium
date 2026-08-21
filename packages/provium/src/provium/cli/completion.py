"""Shell completion activation for the command-line parser."""

import argparse
from importlib import import_module
from typing import Protocol, cast


class _Argcomplete(Protocol):
    def autocomplete(self, parser: argparse.ArgumentParser) -> None: ...


def enable_completion(parser: argparse.ArgumentParser) -> None:
    """Respond to an argcomplete request before normal argument parsing."""
    try:
        argcomplete = cast(_Argcomplete, import_module("argcomplete"))
    except ModuleNotFoundError:
        return
    argcomplete.autocomplete(parser)


__all__ = ["enable_completion"]
