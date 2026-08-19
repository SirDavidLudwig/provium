"""Provium's command-line entry point."""

from .command import Command


def main() -> int:
    """Run the Provium command-line interface."""
    return 0


__all__ = ["Command", "main"]
