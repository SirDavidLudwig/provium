from __future__ import annotations

import pytest

from provium import Artifact, ArtifactCatalog, ArtifactReader, ArtifactWriter


class Reader(ArtifactReader):
    pass


class Writer(ArtifactWriter):
    pass


Integer = Artifact("Integer", reader=Reader, writer=Writer)
Other = Artifact("Other", reader=Reader, writer=Writer)


def test_registers_and_resolves_canonical_identifier() -> None:
    catalog = ArtifactCatalog()

    registration = catalog.register("example.IntegerV1", Integer)

    assert registration.canonical_identifier == "example.IntegerV1"
    assert registration.artifact is Integer
    assert catalog.resolve("example.IntegerV1") is registration
    assert catalog.registration_for(Integer) is registration
    assert dict(catalog.registrations) == {"example.IntegerV1": registration}


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


def test_rejects_inconsistent_registration_of_same_artifact() -> None:
    catalog = ArtifactCatalog()
    catalog.register("example.IntegerV1", Integer)

    with pytest.raises(ValueError, match="artifact"):
        catalog.register("example.IntegerV2", Integer)


def test_registration_validates_identifier() -> None:
    with pytest.raises(ValueError, match="identifier"):
        ArtifactCatalog().register("", Integer)


def test_registration_requires_an_artifact_instance() -> None:
    with pytest.raises(TypeError, match="Artifact"):
        ArtifactCatalog().register(
            "example.InvalidV1",
            object,  # type: ignore[arg-type]
        )
