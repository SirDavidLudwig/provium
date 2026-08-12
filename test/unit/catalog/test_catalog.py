from __future__ import annotations

import pytest

from provium import Artifact, ArtifactCatalog, ArtifactReader, ArtifactWriter


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


def test_registers_and_resolves_canonical_identifier_and_aliases() -> None:
    catalog = ArtifactCatalog()

    registration = catalog.register(
        "example.IntegerV1",
        Integer,
        aliases=("example.LegacyIntegerV1", "example.OldIntegerV1"),
    )

    assert registration.canonical_identifier == "example.IntegerV1"
    assert registration.artifact is Integer
    assert registration.aliases == (
        "example.LegacyIntegerV1",
        "example.OldIntegerV1",
    )
    assert catalog.resolve("example.IntegerV1") is registration
    assert catalog.resolve("example.LegacyIntegerV1") is registration
    assert catalog.resolve("example.OldIntegerV1") is registration
    assert catalog.registration_for(Integer) is registration


def test_alias_resolution_retains_canonical_registration() -> None:
    catalog = ArtifactCatalog()
    registration = catalog.register(
        "example.IntegerV1",
        Integer,
        aliases=("example.LegacyIntegerV1",),
    )

    resolved = catalog.resolve("example.LegacyIntegerV1")

    assert resolved.canonical_identifier == registration.canonical_identifier
    assert resolved.artifact is Integer


def test_unknown_identifiers_and_artifacts_are_not_registered() -> None:
    catalog = ArtifactCatalog()

    with pytest.raises(KeyError):
        catalog.resolve("example.UnknownV1")
    with pytest.raises(KeyError):
        catalog.registration_for(Integer)


def test_rejects_duplicate_canonical_identifier() -> None:
    catalog = ArtifactCatalog()
    catalog.register("example.IntegerV1", Integer)

    with pytest.raises(ValueError, match="canonical identifier"):
        catalog.register("example.IntegerV1", Other)


def test_rejects_duplicate_alias() -> None:
    catalog = ArtifactCatalog()
    catalog.register("example.IntegerV1", Integer, aliases=("example.LegacyV1",))

    with pytest.raises(ValueError, match="alias"):
        catalog.register("example.OtherV1", Other, aliases=("example.LegacyV1",))


def test_rejects_alias_and_canonical_collisions_in_both_directions() -> None:
    catalog = ArtifactCatalog()
    catalog.register("example.IntegerV1", Integer, aliases=("example.LegacyV1",))

    with pytest.raises(ValueError, match="canonical identifier"):
        catalog.register("example.LegacyV1", Other)
    with pytest.raises(ValueError, match="alias"):
        catalog.register("example.OtherV1", Other, aliases=("example.IntegerV1",))


def test_rejects_inconsistent_registration_of_same_artifact_class() -> None:
    catalog = ArtifactCatalog()
    catalog.register("example.IntegerV1", Integer)

    with pytest.raises(ValueError, match="artifact class"):
        catalog.register("example.IntegerV2", Integer)


@pytest.mark.parametrize(
    ("identifier", "aliases", "message"),
    [
        ("", (), "identifier"),
        ("example.IntegerV1", ("",), "alias"),
        ("example.IntegerV1", ("same", "same"), "duplicate alias"),
        ("example.IntegerV1", ("example.IntegerV1",), "alias"),
    ],
)
def test_registration_validates_identifiers(
    identifier: str, aliases: tuple[str, ...], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        ArtifactCatalog().register(identifier, Integer, aliases=aliases)


def test_registration_requires_an_artifact_class() -> None:
    with pytest.raises(TypeError, match="Artifact"):
        ArtifactCatalog().register("example.InvalidV1", object)  # type: ignore[arg-type]
