from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

import pytest

from provium import Artifact, ArtifactCatalog, ArtifactReader, ArtifactWriter
from provium.artifact.discovery import discover_catalogs, reset_discovery


class Reader(ArtifactReader):
    pass


class Writer(ArtifactWriter):
    pass


class Integer(Artifact[Reader, Writer]):
    reader = Reader
    writer = Writer


class Other(Artifact[Reader, Writer]):
    reader = Reader
    writer = Writer


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
    reset_discovery()
    FakeEntryPoints.selected_groups.clear()
    yield
    reset_discovery()


def catalog(
    identifier: str,
    artifact: type[Artifact],
    *,
    aliases: tuple[str, ...] = (),
) -> ArtifactCatalog:
    result = ArtifactCatalog()
    result.register(identifier, artifact, aliases=aliases)
    return result


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


def test_discovers_one_catalog_and_uses_expected_entry_point_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_entry_points(monkeypatch, catalog("example.IntegerV1", Integer))

    discovered = discover_catalogs()

    assert discovered.resolve("example.IntegerV1").artifact is Integer
    assert FakeEntryPoints.selected_groups == ["provium.catalogs"]


def test_discovers_multiple_catalogs_and_resolves_aliases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_entry_points(
        monkeypatch,
        catalog(
            "example.IntegerV1",
            Integer,
            aliases=("example.LegacyIntegerV1",),
        ),
        catalog("example.OtherV1", Other),
    )

    discovered = discover_catalogs()

    assert discovered.resolve("example.LegacyIntegerV1").artifact is Integer
    assert discovered.resolve("example.OtherV1").artifact is Other
    assert (
        discovered.registration_for(Integer).canonical_identifier == "example.IntegerV1"
    )


def test_discovery_is_cached_until_reset(monkeypatch: pytest.MonkeyPatch) -> None:
    points = install_entry_points(monkeypatch, catalog("example.IntegerV1", Integer))

    first = discover_catalogs()
    assert discover_catalogs() is first
    assert points[0].loads == 1

    reset_discovery()
    second = discover_catalogs()
    assert second is not first
    assert points[0].loads == 2


@pytest.mark.parametrize(
    ("first", "second", "message"),
    [
        (
            catalog("example.SharedV1", Integer),
            catalog("example.SharedV1", Other),
            "canonical identifier",
        ),
        (
            catalog("example.IntegerV1", Integer, aliases=("example.SharedV1",)),
            catalog("example.OtherV1", Other, aliases=("example.SharedV1",)),
            "alias",
        ),
        (
            catalog("example.IntegerV1", Integer, aliases=("example.SharedV1",)),
            catalog("example.SharedV1", Other),
            "canonical identifier",
        ),
        (
            catalog("example.SharedV1", Integer),
            catalog("example.OtherV1", Other, aliases=("example.SharedV1",)),
            "alias",
        ),
    ],
)
def test_detects_conflicts_across_catalogs(
    monkeypatch: pytest.MonkeyPatch,
    first: ArtifactCatalog,
    second: ArtifactCatalog,
    message: str,
) -> None:
    install_entry_points(monkeypatch, first, second)

    with pytest.raises(ValueError, match=message):
        discover_catalogs()


def test_rejects_entry_point_that_is_not_a_catalog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_entry_points(monkeypatch, object())

    with pytest.raises(TypeError, match="ArtifactCatalog"):
        discover_catalogs()


def test_failed_discovery_is_not_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    points = install_entry_points(monkeypatch, object())

    with pytest.raises(TypeError):
        discover_catalogs()
    with pytest.raises(TypeError):
        discover_catalogs()

    assert points[0].loads == 2


def test_empty_discovery_returns_empty_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    install_entry_points(monkeypatch)

    discovered = discover_catalogs()

    with pytest.raises(KeyError):
        discovered.resolve("example.UnknownV1")
