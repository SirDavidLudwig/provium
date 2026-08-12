"""Discover explicitly published artifact catalogs through package entry points."""

from __future__ import annotations

from importlib import metadata

from .catalog import ArtifactCatalog

ENTRY_POINT_GROUP = "provium.catalogs"
_discovered_catalog: ArtifactCatalog | None = None


def discover_catalogs() -> ArtifactCatalog:
    """Load and combine installed catalogs, caching a successful discovery."""
    global _discovered_catalog
    if _discovered_catalog is not None:
        return _discovered_catalog

    discovered = ArtifactCatalog()
    for entry_point in metadata.entry_points().select(group=ENTRY_POINT_GROUP):
        catalog = entry_point.load()
        if not isinstance(catalog, ArtifactCatalog):
            message = (
                f"catalog entry point {entry_point.name!r} must expose "
                "an ArtifactCatalog"
            )
            raise TypeError(message)
        for registration in catalog.registrations.values():
            discovered.register(
                registration.canonical_identifier,
                registration.artifact,
                aliases=registration.aliases,
            )
    _discovered_catalog = discovered
    return discovered


def reset_discovery() -> None:
    """Clear cached discovery state, primarily for isolated tests."""
    global _discovered_catalog
    _discovered_catalog = None


__all__ = ["discover_catalogs", "reset_discovery"]
