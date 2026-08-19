from __future__ import annotations

import tomllib
from pathlib import Path

from provium_cli import CommandCatalog


def test_core_catalog_starts_empty() -> None:
    from provium_cli.commands import catalog

    assert isinstance(catalog, CommandCatalog)
    assert catalog.commands == {}


def test_project_publishes_the_core_command_catalog() -> None:
    project_root = Path(__file__).parents[3]
    configuration = tomllib.loads(
        (project_root / "pyproject.toml").read_text(encoding="utf-8")
    )

    assert configuration["project"]["entry-points"]["provium_cli.command_catalogs"] == {
        "core": "provium_cli.commands:catalog"
    }
