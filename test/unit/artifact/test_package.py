from provium.artifact import (
    Artifact,
    ArtifactCatalog,
    ArtifactHeader,
    ArtifactReader,
    ArtifactRegistration,
    ArtifactWriter,
    BodyRegion,
    BoundReadArtifact,
    BoundWriteArtifact,
    JsonArtifact,
    JsonArtifactReader,
    JsonArtifactWriter,
    decode_header,
    discover_catalogs,
    encode_header,
    open_artifact,
    reset_discovery,
)
from provium.artifact.prefab import (
    JsonArtifact as PrefabJsonArtifact,
)
from provium.artifact.prefab import (
    JsonArtifactReader as PrefabJsonArtifactReader,
)
from provium.artifact.prefab import (
    JsonArtifactWriter as PrefabJsonArtifactWriter,
)


def test_artifact_package_exports_the_complete_subsystem() -> None:
    assert all(
        value is not None
        for value in (
            Artifact,
            ArtifactCatalog,
            ArtifactHeader,
            ArtifactReader,
            ArtifactRegistration,
            ArtifactWriter,
            BodyRegion,
            BoundReadArtifact,
            BoundWriteArtifact,
            JsonArtifact,
            JsonArtifactReader,
            JsonArtifactWriter,
            decode_header,
            discover_catalogs,
            encode_header,
            open_artifact,
            reset_discovery,
        )
    )


def test_prefab_package_exports_json_artifact_types() -> None:
    assert PrefabJsonArtifact is JsonArtifact
    assert PrefabJsonArtifactReader is JsonArtifactReader
    assert PrefabJsonArtifactWriter is JsonArtifactWriter
