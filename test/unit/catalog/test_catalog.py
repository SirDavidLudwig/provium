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


Integer = Artifact("example.IntegerV1", "Integer", Reader, Writer)
Other = Artifact("example.OtherV1", "Other", Reader, Writer)
IntegerDefinition = ArtifactDefinition(
    "example.IntegerV1",
    "example.artifacts:Integer",
    "An integer artifact.",
)


def test_registers_and_resolves_definition_without_loading_target() -> None:
    catalog = ArtifactCatalog()

    registered = catalog.register(IntegerDefinition)

    assert registered is IntegerDefinition
    assert catalog.resolve("example.IntegerV1") is IntegerDefinition
    assert dict(catalog.definitions) == {"example.IntegerV1": IntegerDefinition}


def test_definition_resolves_and_validates_its_lazy_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    imports: list[str] = []

    def import_module(name: str) -> object:
        imports.append(name)
        return SimpleNamespace(nested=SimpleNamespace(Integer=Integer))

    monkeypatch.setattr("provium.artifact.catalog.import_module", import_module)
    definition = ArtifactDefinition[Artifact[Reader, Writer]](
        "example.IntegerV1", "example.artifacts:nested.Integer", "An integer."
    )

    assert imports == []
    assert definition.resolve() is Integer
    assert imports == ["example.artifacts"]


@pytest.mark.parametrize(
    ("resolved", "error", "message"),
    [
        (object(), TypeError, "Artifact"),
        (Other, ValueError, "identifier"),
    ],
)
def test_definition_rejects_an_invalid_resolved_target(
    monkeypatch: pytest.MonkeyPatch,
    resolved: object,
    error: type[Exception],
    message: str,
) -> None:
    monkeypatch.setattr(
        "provium.artifact.catalog.import_module",
        lambda name: SimpleNamespace(value=resolved),
    )
    definition = ArtifactDefinition(
        "example.IntegerV1", "example.artifacts:value", "An integer."
    )

    with pytest.raises(error, match=message):
        definition.resolve()


@pytest.mark.parametrize(
    ("identifier", "target", "description", "message"),
    [
        ("", "example.artifacts:value", "Description", "identifier"),
        ("example.IntegerV1", "", "Description", "target"),
        ("example.IntegerV1", "example.artifacts:value", "", "description"),
        ("example.IntegerV1", "missing-colon", "Description", "module:attribute"),
        ("example.IntegerV1", ":value", "Description", "module:attribute"),
        ("example.IntegerV1", "example.artifacts:", "Description", "module:attribute"),
    ],
)
def test_definition_validates_its_schema(
    identifier: str, target: str, description: str, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        ArtifactDefinition(identifier, target, description)


def test_unknown_identifier_is_not_registered() -> None:
    with pytest.raises(KeyError):
        ArtifactCatalog().resolve("example.UnknownV1")


def test_rejects_duplicate_identifier() -> None:
    catalog = ArtifactCatalog()
    catalog.register(IntegerDefinition)

    with pytest.raises(ValueError, match="identifier"):
        catalog.register(
            ArtifactDefinition(
                "example.IntegerV1", "example.artifacts:Other", "Another artifact."
            )
        )


def test_registration_requires_a_definition() -> None:
    with pytest.raises(TypeError, match="ArtifactDefinition"):
        ArtifactCatalog().register(Integer)  # type: ignore[arg-type]
