from collections.abc import Callable
from pathlib import Path
from typing import Any, ClassVar, get_type_hints

from provium import (
    Artifact,
    ArtifactCatalog,
    ArtifactDefinition,
    ArtifactReader,
    ArtifactWriter,
)


def test_artifact_metadata_retains_its_generic_reader_and_writer_types() -> None:
    reader_type, writer_type = Artifact.__type_params__
    annotations = get_type_hints(Artifact)

    assert reader_type.__bound__ is ArtifactReader
    assert writer_type.__bound__ is ArtifactWriter
    assert annotations["reader"] == type[reader_type]
    assert annotations["writer"] == type[writer_type]
    assert annotations["dump"] == Callable[[reader_type, Path], None] | None
    assert annotations["load"] == Callable[[Path, writer_type], None] | None


def test_artifact_definition_preserves_its_concrete_artifact_type() -> None:
    (artifact_type,) = ArtifactDefinition.__type_params__
    resolve_annotations = get_type_hints(
        ArtifactDefinition.resolve,
        localns={"ArtifactT": artifact_type},
    )

    assert artifact_type.__bound__ == Artifact[Any, Any]
    assert get_type_hints(Artifact)["definition"] == ClassVar[ArtifactDefinition[Any]]
    assert resolve_annotations["return"] == type[artifact_type]


def test_artifact_catalog_registration_preserves_the_concrete_artifact_type() -> None:
    (artifact_type,) = ArtifactCatalog.register.__type_params__
    annotations = get_type_hints(
        ArtifactCatalog.register,
        localns={"ArtifactT": artifact_type},
    )

    assert artifact_type.__bound__ == Artifact[Any, Any]
    assert annotations["definition"] == ArtifactDefinition[artifact_type]
    assert annotations["return"] == ArtifactDefinition[artifact_type]
