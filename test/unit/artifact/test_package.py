from provium.artifact import (
    Artifact,
    ArtifactCatalog,
    ArtifactHeader,
    ArtifactReader,
    ArtifactRegistration,
    ArtifactWriter,
    BodyRegion,
    decode_header,
    discover_catalogs,
    encode_header,
    open_artifact,
    reset_discovery,
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
            decode_header,
            discover_catalogs,
            encode_header,
            open_artifact,
            reset_discovery,
        )
    )
