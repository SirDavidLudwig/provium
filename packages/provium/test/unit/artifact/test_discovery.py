from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

import pytest

from provium import (
    ArtifactCatalog,
    ArtifactDefinition,
    discover_artifact_catalogs,
    reset_artifact_discovery,
)


@dataclass
class FakeEntryPoint:
    name: str
    value: object
    loads: int = 0

    def load(self) -> object:
        self.loads += 1
        return self.value


class FakeEntryPoints(list[FakeEntryPoint]):
    selected_groups: ClassVar[list[str]] = []

    def select(self, *, group: str) -> FakeEntryPoints:
        self.selected_groups.append(group)
        return self


@pytest.fixture(autouse=True)
def isolated_discovery() -> None:
    reset_artifact_discovery()
    FakeEntryPoints.selected_groups.clear()
    yield
    reset_artifact_discovery()


def make_catalog(identifier: str) -> ArtifactCatalog:
    catalog = ArtifactCatalog()
    catalog.register(
        ArtifactDefinition(identifier, "example.artifacts:Artifact", "An artifact.")
    )
    return catalog


def install_entry_points(
    monkeypatch: pytest.MonkeyPatch, *values: object
) -> list[FakeEntryPoint]:
    points = [
        FakeEntryPoint(f"catalog-{index}", value) for index, value in enumerate(values)
    ]
    monkeypatch.setattr(
        "provium.artifact.discovery.metadata.entry_points",
        lambda: FakeEntryPoints(points),
    )
    return points


def test_discovers_and_merges_artifact_catalogs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_entry_points(
        monkeypatch,
        make_catalog("example.FirstV1"),
        make_catalog("example.SecondV1"),
    )

    discovered = discover_artifact_catalogs()

    assert set(discovered.definitions) == {"example.FirstV1", "example.SecondV1"}
    assert FakeEntryPoints.selected_groups == ["provium.artifact_catalogs"]


def test_discovery_is_cached_until_reset(monkeypatch: pytest.MonkeyPatch) -> None:
    points = install_entry_points(monkeypatch, make_catalog("example.FirstV1"))

    first = discover_artifact_catalogs()
    assert discover_artifact_catalogs() is first
    assert points[0].loads == 1

    reset_artifact_discovery()
    assert discover_artifact_catalogs() is not first
    assert points[0].loads == 2


def test_discovery_rejects_invalid_catalogs_without_caching(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    points = install_entry_points(monkeypatch, object())

    with pytest.raises(TypeError, match="ArtifactCatalog"):
        discover_artifact_catalogs()
    with pytest.raises(TypeError, match="ArtifactCatalog"):
        discover_artifact_catalogs()

    assert points[0].loads == 2


def test_discovery_rejects_duplicate_identifiers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_entry_points(
        monkeypatch,
        make_catalog("example.SharedV1"),
        make_catalog("example.SharedV1"),
    )

    with pytest.raises(ValueError, match="already registered"):
        discover_artifact_catalogs()


def test_empty_discovery_returns_an_empty_catalog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_entry_points(monkeypatch)

    assert dict(discover_artifact_catalogs().definitions) == {}
