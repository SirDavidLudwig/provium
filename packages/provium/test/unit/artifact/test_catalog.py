from __future__ import annotations

from types import SimpleNamespace

import pytest

from provium import Artifact, ArtifactCatalog, ArtifactDefinition

INTEGER_DEFINITION = ArtifactDefinition(
    "example.IntegerV1",
    "example.artifacts:IntegerArtifact",
    "An integer artifact.",
)


class IntegerArtifact(Artifact[object, object]):
    definition = INTEGER_DEFINITION


def test_catalog_registers_definitions_without_resolving_them() -> None:
    catalog = ArtifactCatalog()

    registered = catalog.register(INTEGER_DEFINITION)

    assert registered is INTEGER_DEFINITION
    assert catalog.resolve("example.IntegerV1") is INTEGER_DEFINITION
    assert dict(catalog.definitions) == {"example.IntegerV1": INTEGER_DEFINITION}


def test_catalog_rejects_invalid_and_duplicate_entries() -> None:
    catalog = ArtifactCatalog()

    with pytest.raises(TypeError, match="ArtifactDefinition"):
        catalog.register(object())  # type: ignore[arg-type]

    catalog.register(INTEGER_DEFINITION)
    with pytest.raises(ValueError, match="already registered"):
        catalog.register(INTEGER_DEFINITION)


def test_catalog_definitions_are_read_only() -> None:
    catalog = ArtifactCatalog()
    catalog.register(INTEGER_DEFINITION)

    with pytest.raises(TypeError):
        catalog.definitions["other"] = INTEGER_DEFINITION  # type: ignore[index]


def test_catalog_raises_for_an_unknown_identifier() -> None:
    with pytest.raises(KeyError):
        ArtifactCatalog().resolve("example.UnknownV1")


def test_definition_lazily_resolves_an_artifact_class(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    imports: list[str] = []

    def import_module(name: str) -> object:
        imports.append(name)
        return SimpleNamespace(nested=SimpleNamespace(Integer=IntegerArtifact))

    monkeypatch.setattr("provium.artifact.definition.import_module", import_module)
    definition = ArtifactDefinition(
        "example.IntegerV1",
        "example.artifacts:nested.Integer",
        "An integer artifact.",
    )
    IntegerArtifact.definition = definition

    assert imports == []
    assert definition.resolve() is IntegerArtifact
    assert imports == ["example.artifacts"]


def test_definition_rejects_a_target_that_is_not_an_artifact_class(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "provium.artifact.definition.import_module",
        lambda name: SimpleNamespace(value=object()),
    )
    definition = ArtifactDefinition(
        "example.IntegerV1", "example.artifacts:value", "An integer artifact."
    )

    with pytest.raises(TypeError, match="Artifact class"):
        definition.resolve()


def test_definition_rejects_an_artifact_with_a_different_definition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "provium.artifact.definition.import_module",
        lambda name: SimpleNamespace(value=IntegerArtifact),
    )
    definition = ArtifactDefinition(
        "example.OtherV1", "example.artifacts:value", "Another artifact."
    )

    with pytest.raises(ValueError, match="definition does not match"):
        definition.resolve()


def test_definition_rejects_an_artifact_without_an_artifact_definition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class AlwaysEqual:
        def __eq__(self, other: object) -> bool:
            return True

    class InvalidArtifact(Artifact[object, object]):
        definition = AlwaysEqual()  # type: ignore[assignment]

    monkeypatch.setattr(
        "provium.artifact.definition.import_module",
        lambda name: SimpleNamespace(value=InvalidArtifact),
    )
    definition = ArtifactDefinition(
        "example.InvalidV1", "example.artifacts:value", "An invalid artifact."
    )

    with pytest.raises(TypeError, match="ArtifactDefinition"):
        definition.resolve()
