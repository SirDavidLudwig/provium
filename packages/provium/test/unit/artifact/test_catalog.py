from __future__ import annotations

from types import SimpleNamespace

import pytest

from provium import (
    Artifact,
    ArtifactCatalog,
    ArtifactDefinition,
    ArtifactReader,
    ArtifactWriter,
)


class Reader(ArtifactReader):
    pass


class Writer(ArtifactWriter):
    pass


INTEGER_DEFINITION = ArtifactDefinition(
    "example.IntegerV1",
    "example.artifacts:IntegerArtifact",
    "An integer artifact.",
)


class IntegerArtifact(Artifact[Reader, Writer]):
    definition = INTEGER_DEFINITION
    reader = Reader
    writer = Writer


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
    monkeypatch.setattr(IntegerArtifact, "definition", definition)

    assert imports == []
    assert definition.resolve() is IntegerArtifact
    assert imports == ["example.artifacts"]


def test_definition_returns_its_target_without_runtime_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    definition = ArtifactDefinition(
        "example.IntegerV1", "example.artifacts:value", "An integer artifact."
    )
    target = SimpleNamespace(definition=definition)
    monkeypatch.setattr(
        "provium.artifact.definition.import_module",
        lambda name: SimpleNamespace(value=target),
    )

    assert definition.resolve() is target


def test_definition_accepts_a_distinct_definition_with_the_same_identity_and_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    definition = ArtifactDefinition(
        "example.IntegerV1", "example.artifacts:value", "An integer artifact."
    )
    compatible_definition = ArtifactDefinition(
        "example.IntegerV1", "example.artifacts:value", "Updated documentation."
    )
    target = SimpleNamespace(definition=compatible_definition)
    monkeypatch.setattr(
        "provium.artifact.definition.import_module",
        lambda name: SimpleNamespace(value=target),
    )

    assert definition.resolve() is target


@pytest.mark.parametrize(
    ("identifier", "target"),
    [
        ("example.OtherV1", "example.artifacts:value"),
        ("example.IntegerV1", "example.artifacts:other"),
    ],
)
def test_definition_rejects_a_target_with_different_resolution_metadata(
    monkeypatch: pytest.MonkeyPatch,
    identifier: str,
    target: str,
) -> None:
    definition = ArtifactDefinition(
        "example.IntegerV1", "example.artifacts:value", "An integer artifact."
    )
    resolved_definition = ArtifactDefinition(identifier, target, "An artifact.")
    resolved_target = SimpleNamespace(definition=resolved_definition)
    monkeypatch.setattr(
        "provium.artifact.definition.import_module",
        lambda name: SimpleNamespace(value=resolved_target),
    )

    with pytest.raises(ValueError, match="identifier and target"):
        definition.resolve()
