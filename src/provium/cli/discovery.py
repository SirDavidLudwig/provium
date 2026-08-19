"""Discover command catalogs published by installed distributions."""

from __future__ import annotations

from importlib import metadata

from .catalog import CommandCatalog

ENTRY_POINT_GROUP = "provium.command_catalogs"
_discovered_catalog: CommandCatalog | None = None


def discover_command_catalogs() -> CommandCatalog:
    """Load and combine installed command catalogs."""
    global _discovered_catalog
    if _discovered_catalog is not None:
        return _discovered_catalog

    discovered = CommandCatalog()
    for entry_point in metadata.entry_points(group=ENTRY_POINT_GROUP):
        catalog = entry_point.load()
        if not isinstance(catalog, CommandCatalog):
            raise TypeError(
                f"command catalog entry point {entry_point.name!r} must expose "
                "a CommandCatalog"
            )
        for command in catalog.commands.values():
            discovered.register(command)

    _discovered_catalog = discovered
    return discovered


def reset_command_discovery() -> None:
    """Clear the cached command catalog discovery result."""
    global _discovered_catalog
    _discovered_catalog = None


__all__ = [
    "ENTRY_POINT_GROUP",
    "discover_command_catalogs",
    "reset_command_discovery",
]
