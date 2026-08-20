from __future__ import annotations

from provium.cli import CommandCatalog
from provium.cli.discovery import discover_command_catalogs


def test_core_catalog_registers_procedure_and_artifact_commands() -> None:
    from provium.cli.commands import catalog

    assert isinstance(catalog, CommandCatalog)
    assert tuple(catalog.commands) == ("procedure", "execute", "artifact")


def test_discovery_always_includes_the_core_command_catalog() -> None:
    assert tuple(discover_command_catalogs().commands) == (
        "procedure",
        "execute",
        "artifact",
    )
