from __future__ import annotations

import argparse
from collections.abc import Callable, Generator
from dataclasses import dataclass

import pytest

from provium.cli import (
    Command,
    CommandCatalog,
    discover_command_catalogs,
    reset_command_discovery,
)
from provium.cli.discovery import ENTRY_POINT_GROUP


class FirstCommand(Command):
    name = "first"
    help = "Run the first command"

    def configure(self, parser: argparse.ArgumentParser) -> None:
        pass

    def execute(self, arguments: argparse.Namespace) -> int:
        return 0


class SecondCommand(FirstCommand):
    name = "second"
    help = "Run the second command"


@dataclass
class EntryPoint:
    name: str
    loader: Callable[[], object]

    def load(self) -> object:
        return self.loader()


@pytest.fixture(autouse=True)
def reset_discovery() -> Generator[None]:
    reset_command_discovery()
    yield
    reset_command_discovery()


def catalog_with(*commands: type[Command]) -> CommandCatalog:
    catalog = CommandCatalog()
    for command in commands:
        catalog.register(command)
    return catalog


def test_discovers_and_combines_installed_catalogs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def entry_points(*, group: str) -> tuple[EntryPoint, ...]:
        calls.append(group)
        return (
            EntryPoint("first-plugin", lambda: catalog_with(FirstCommand)),
            EntryPoint("second-plugin", lambda: catalog_with(SecondCommand)),
        )

    monkeypatch.setattr("provium.cli.discovery.metadata.entry_points", entry_points)

    discovered = discover_command_catalogs()

    assert calls == [ENTRY_POINT_GROUP]
    assert discovered.commands == {
        "first": FirstCommand,
        "second": SecondCommand,
    }


def test_empty_discovery_returns_an_empty_catalog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "provium.cli.discovery.metadata.entry_points",
        lambda *, group: (),
    )

    assert discover_command_catalogs().commands == {}


def test_successful_discovery_is_cached_until_reset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def entry_points(*, group: str) -> tuple[EntryPoint, ...]:
        nonlocal calls
        calls += 1
        return (EntryPoint("plugin", lambda: catalog_with(FirstCommand)),)

    monkeypatch.setattr("provium.cli.discovery.metadata.entry_points", entry_points)

    first = discover_command_catalogs()
    second = discover_command_catalogs()
    reset_command_discovery()
    third = discover_command_catalogs()

    assert first is second
    assert third is not first
    assert calls == 2


def test_rejects_entry_points_that_do_not_load_catalogs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "provium.cli.discovery.metadata.entry_points",
        lambda *, group: (EntryPoint("broken", object),),
    )

    with pytest.raises(TypeError, match="broken"):
        discover_command_catalogs()


def test_rejects_duplicate_commands_across_catalogs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class DuplicateCommand(FirstCommand):
        pass

    monkeypatch.setattr(
        "provium.cli.discovery.metadata.entry_points",
        lambda *, group: (
            EntryPoint("first", lambda: catalog_with(FirstCommand)),
            EntryPoint("duplicate", lambda: catalog_with(DuplicateCommand)),
        ),
    )

    with pytest.raises(ValueError, match="already registered"):
        discover_command_catalogs()


def test_failed_discovery_is_not_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    results: list[tuple[EntryPoint, ...]] = [
        (EntryPoint("broken", object),),
        (EntryPoint("valid", lambda: catalog_with(FirstCommand)),),
    ]
    monkeypatch.setattr(
        "provium.cli.discovery.metadata.entry_points",
        lambda *, group: results.pop(0),
    )

    with pytest.raises(TypeError):
        discover_command_catalogs()

    assert discover_command_catalogs().resolve("first") is FirstCommand
