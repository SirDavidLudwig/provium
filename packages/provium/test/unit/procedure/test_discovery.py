from dataclasses import dataclass

import pytest

from provium import (
    ProcedureCatalog,
    ProcedureContract,
    ProcedureDefinition,
    discover_procedure_catalogs,
    reset_procedure_discovery,
)


class Contract(ProcedureContract[None]):
    pass


@dataclass
class EntryPoint:
    name: str
    value: object

    def load(self) -> object:
        return self.value


@pytest.fixture(autouse=True)
def isolated_discovery() -> None:
    reset_procedure_discovery()
    yield
    reset_procedure_discovery()


def catalog(identifier: str) -> ProcedureCatalog:
    result = ProcedureCatalog()
    result.register(
        ProcedureDefinition(
            identifier,
            "example.procedures:Procedure",
            "Example",
            None,
            Contract,
        )
    )
    return result


def test_discovers_and_merges_procedure_catalogs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    groups: list[str] = []

    def entry_points(*, group: str) -> tuple[EntryPoint, ...]:
        groups.append(group)
        return (
            EntryPoint("first", catalog("example.FirstV1")),
            EntryPoint("second", catalog("example.SecondV1")),
        )

    monkeypatch.setattr(
        "provium.procedure.discovery.metadata.entry_points", entry_points
    )

    discovered = discover_procedure_catalogs()

    assert set(discovered.definitions) == {"example.FirstV1", "example.SecondV1"}
    assert groups == ["provium.procedure_catalogs"]


def test_successful_discovery_is_cached_and_resettable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def entry_points(*, group: str) -> tuple[EntryPoint, ...]:
        nonlocal calls
        calls += 1
        return (EntryPoint("example", catalog("example.ExampleV1")),)

    monkeypatch.setattr(
        "provium.procedure.discovery.metadata.entry_points", entry_points
    )

    first = discover_procedure_catalogs()
    assert discover_procedure_catalogs() is first
    reset_procedure_discovery()
    assert discover_procedure_catalogs() is not first
    assert calls == 2


def test_failed_discovery_is_not_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def entry_points(*, group: str) -> tuple[EntryPoint, ...]:
        nonlocal calls
        calls += 1
        return (EntryPoint("invalid", object()),)

    monkeypatch.setattr(
        "provium.procedure.discovery.metadata.entry_points", entry_points
    )

    with pytest.raises(TypeError, match="ProcedureCatalog"):
        discover_procedure_catalogs()
    with pytest.raises(TypeError, match="ProcedureCatalog"):
        discover_procedure_catalogs()
    assert calls == 2


def test_discovery_rejects_duplicate_identifiers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "provium.procedure.discovery.metadata.entry_points",
        lambda *, group: (
            EntryPoint("first", catalog("example.SharedV1")),
            EntryPoint("second", catalog("example.SharedV1")),
        ),
    )

    with pytest.raises(ValueError, match="already registered"):
        discover_procedure_catalogs()


def test_empty_discovery_returns_an_empty_catalog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "provium.procedure.discovery.metadata.entry_points",
        lambda *, group: (),
    )

    assert dict(discover_procedure_catalogs().definitions) == {}
