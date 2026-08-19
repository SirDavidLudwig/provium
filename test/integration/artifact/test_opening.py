from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from provium import (
    Artifact,
    ArtifactCatalog,
    ArtifactDefinition,
    ArtifactHeader,
    ArtifactLineage,
    ArtifactReader,
    ArtifactRecord,
    ArtifactReference,
    ArtifactWriter,
    Procedure,
    ProcedureExecutionRecord,
    ProcedureRecord,
    encode_header,
    open_artifact,
)


class BytesReader(ArtifactReader):
    def read(self) -> bytes:
        return self.body.read()


class BytesWriter(ArtifactWriter):
    pass


BytesArtifact = Artifact("example.BytesV1", "Bytes", BytesReader, BytesWriter)


class OtherReader(ArtifactReader):
    pass


class OtherWriter(ArtifactWriter):
    pass


OtherArtifact = Artifact("example.OtherV1", "Other", OtherReader, OtherWriter)


class BrokenReader(ArtifactReader):
    def __init__(self, *args: object, **kwargs: object) -> None:
        raise RuntimeError("reader construction failed")


BrokenArtifact = Artifact("example.BrokenV1", "Broken", BrokenReader, OtherWriter)


@pytest.fixture
def discovered_catalog(monkeypatch: pytest.MonkeyPatch) -> ArtifactCatalog:
    catalog = ArtifactCatalog()
    catalog.register(
        ArtifactDefinition("example.BytesV1", f"{__name__}:BytesArtifact", "Bytes.")
    )
    catalog.register(
        ArtifactDefinition("example.OtherV1", f"{__name__}:OtherArtifact", "Other.")
    )
    catalog.register(
        ArtifactDefinition("example.BrokenV1", f"{__name__}:BrokenArtifact", "Broken.")
    )
    monkeypatch.setattr("provium.procedure.discover_catalogs", lambda: catalog)
    return catalog


def write_artifact(
    path: Path,
    body: bytes,
    *,
    identity: str,
    identifier: str = "example.BytesV1",
    input_lineages: tuple[ArtifactLineage, ...] = (),
    inputs: tuple[ArtifactReference, ...] = (),
) -> tuple[ArtifactReference, ArtifactLineage]:
    reference = ArtifactReference(identity, identifier)
    execution = ProcedureExecutionRecord(
        f"execution-{identity}",
        ProcedureRecord("fixture", "1"),
        inputs,
        (reference,),
    )
    digest = hashlib.sha256(body).hexdigest()
    lineage = ArtifactLineage.for_execution(
        execution,
        (ArtifactRecord(reference, digest, execution.identity),),
        input_lineages,
    )
    header = ArtifactHeader(
        artifact_identifier=identifier,
        artifact_identity=identity,
        body_offset=4096,
        body_length=len(body),
        body_digest=digest,
        lineage=lineage,
    )
    encoded = encode_header(header)
    path.write_bytes(encoded + bytes(header.body_offset - len(encoded)) + body)
    return reference, lineage


def test_opens_with_concrete_artifact_and_tracks_input(
    tmp_path: Path, discovered_catalog: ArtifactCatalog
) -> None:
    path = tmp_path / "value.pa"
    reference, lineage = write_artifact(path, b"value", identity="artifact-1")

    with Procedure("consume", "1").execute() as execution:
        reader = BytesArtifact.open(path)
        assert isinstance(reader, BytesReader)
        assert reader.read() == b"value"
        assert execution.inputs == (lineage.artifact(reference),)
        assert execution.input_lineage == lineage
        assert execution.readers == (reader,)


def test_opens_unregistered_artifact_with_concrete_type(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "value.pa"
    identifier = BytesArtifact.identifier
    reference, lineage = write_artifact(
        path,
        b"value",
        identity="artifact-1",
        identifier=identifier,
    )
    monkeypatch.setattr(
        "provium.procedure.discover_catalogs",
        lambda: ArtifactCatalog(),
    )

    with Procedure("consume", "1").execute() as execution:
        reader = BytesArtifact.open(path)

        assert reader.read() == b"value"
        assert execution.inputs == (lineage.artifact(reference),)
        assert execution.input_definitions == ()


def test_typed_open_does_not_resolve_a_registered_lazy_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "value.pa"
    write_artifact(path, b"value", identity="artifact-1")
    definition = ArtifactDefinition(
        BytesArtifact.identifier,
        "package_that_does_not_exist:BytesArtifact",
        "Bytes.",
    )
    catalog = ArtifactCatalog()
    catalog.register(definition)
    monkeypatch.setattr("provium.procedure.discover_catalogs", lambda: catalog)

    with Procedure("consume", "1").execute() as execution:
        assert BytesArtifact.open(path).read() == b"value"
        assert execution.input_definitions == (definition,)


def test_generic_open_still_requires_dynamic_registration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "value.pa"
    identifier = BytesArtifact.identifier
    write_artifact(path, b"value", identity="artifact-1", identifier=identifier)
    monkeypatch.setattr(
        "provium.procedure.discover_catalogs",
        lambda: ArtifactCatalog(),
    )

    with (
        Procedure("consume", "1").execute(),
        pytest.raises(ValueError, match="unknown artifact identifier"),
    ):
        open_artifact(path)


def test_expected_definition_opens_an_unregistered_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "value.pa"
    write_artifact(
        path,
        b"value",
        identity="artifact-1",
        identifier=BytesArtifact.identifier,
    )
    monkeypatch.setattr("provium.procedure.discover_catalogs", ArtifactCatalog)

    with Procedure("consume", "1").execute():
        reader = open_artifact(path, expected=BytesArtifact)

        assert isinstance(reader, BytesReader)
        assert reader.read() == b"value"


def test_expected_definition_rejects_a_different_unregistered_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "value.pa"
    write_artifact(
        path,
        b"value",
        identity="artifact-1",
        identifier=BytesArtifact.identifier,
    )
    monkeypatch.setattr("provium.procedure.discover_catalogs", ArtifactCatalog)

    with (
        Procedure("consume", "1").execute(),
        pytest.raises(TypeError, match="expected"),
    ):
        open_artifact(path, expected=OtherArtifact)


def test_opens_dynamically_and_resolves_concrete_reader(
    tmp_path: Path, discovered_catalog: ArtifactCatalog
) -> None:
    path = tmp_path / "value.pa"
    write_artifact(path, b"dynamic", identity="artifact-1")

    with Procedure("consume", "1").execute():
        reader = open_artifact(path)

        assert isinstance(reader, BytesReader)
        assert reader.body.read() == b"dynamic"


def test_expected_type_accepts_one_or_multiple_artifacts(
    tmp_path: Path, discovered_catalog: ArtifactCatalog
) -> None:
    path = tmp_path / "value.pa"
    write_artifact(path, b"value", identity="artifact-1")

    with Procedure("consume", "1").execute():
        assert isinstance(open_artifact(path, expected=BytesArtifact), BytesReader)
        assert isinstance(
            open_artifact(path, expected=(OtherArtifact, BytesArtifact)),
            BytesReader,
        )


def test_expected_type_rejects_artifact_outside_set(
    tmp_path: Path, discovered_catalog: ArtifactCatalog
) -> None:
    path = tmp_path / "value.pa"
    write_artifact(path, b"value", identity="artifact-1")

    with (
        Procedure("consume", "1").execute(),
        pytest.raises(TypeError, match="expected"),
    ):
        open_artifact(path, expected=OtherArtifact)


def test_typed_open_rejects_different_artifact_type(
    tmp_path: Path, discovered_catalog: ArtifactCatalog
) -> None:
    path = tmp_path / "other.pa"
    write_artifact(
        path,
        b"other",
        identity="other-1",
        identifier="example.OtherV1",
    )

    with (
        Procedure("consume", "1").execute(),
        pytest.raises(TypeError, match="requested"),
    ):
        BytesArtifact.open(path)


def test_rejects_unknown_artifact_identifier(
    tmp_path: Path, discovered_catalog: ArtifactCatalog
) -> None:
    path = tmp_path / "unknown.pa"
    write_artifact(path, b"value", identity="artifact-1", identifier="unknown.TypeV1")

    with (
        Procedure("consume", "1").execute(),
        pytest.raises(ValueError, match="unknown artifact identifier"),
    ):
        open_artifact(path)


def test_same_artifact_deduplicates_input_but_tracks_each_reader(
    tmp_path: Path, discovered_catalog: ArtifactCatalog
) -> None:
    path = tmp_path / "value.pa"
    write_artifact(path, b"value", identity="artifact-1")

    with Procedure("consume", "1").execute() as execution:
        first = BytesArtifact.open(path)
        second = BytesArtifact.open(path)

        assert len(execution.inputs) == 1
        assert execution.readers == (first, second)
        assert first is not second


def test_merges_complete_branching_input_lineage(
    tmp_path: Path, discovered_catalog: ArtifactCatalog
) -> None:
    root_path = tmp_path / "root.pa"
    root, root_lineage = write_artifact(root_path, b"root", identity="root")
    left_path = tmp_path / "left.pa"
    _, left_lineage = write_artifact(
        left_path,
        b"left",
        identity="left",
        inputs=(root,),
        input_lineages=(root_lineage,),
    )
    right_path = tmp_path / "right.pa"
    _, right_lineage = write_artifact(
        right_path,
        b"right",
        identity="right",
        inputs=(root,),
        input_lineages=(root_lineage,),
    )

    with Procedure("join", "1").execute() as execution:
        BytesArtifact.open(left_path)
        BytesArtifact.open(right_path)

        assert set(execution.input_lineage.artifacts) == {"root", "left", "right"}
        assert len(execution.input_lineage.executions) == 3
        assert execution.input_lineage == left_lineage.merge(right_lineage)


def test_rejects_modified_body_digest(
    tmp_path: Path, discovered_catalog: ArtifactCatalog
) -> None:
    path = tmp_path / "corrupt.pa"
    write_artifact(path, b"value", identity="artifact-1")
    encoded = bytearray(path.read_bytes())
    encoded[-1] ^= 1
    path.write_bytes(encoded)

    with Procedure("consume", "1").execute(), pytest.raises(ValueError, match="digest"):
        BytesArtifact.open(path)


def test_rejects_truncated_body(
    tmp_path: Path, discovered_catalog: ArtifactCatalog
) -> None:
    path = tmp_path / "truncated.pa"
    write_artifact(path, b"value", identity="artifact-1")
    path.write_bytes(path.read_bytes()[:-1])

    with (
        Procedure("consume", "1").execute(),
        pytest.raises(ValueError, match="truncated"),
    ):
        BytesArtifact.open(path)


def test_rejects_lineage_missing_opened_identity(
    tmp_path: Path, discovered_catalog: ArtifactCatalog
) -> None:
    path = tmp_path / "identity.pa"
    _, original_lineage = write_artifact(path, b"value", identity="artifact-1")
    body = b"value"
    header = ArtifactHeader(
        artifact_identifier="example.BytesV1",
        artifact_identity="different-identity",
        body_offset=4096,
        body_length=len(body),
        body_digest=hashlib.sha256(body).hexdigest(),
        lineage=original_lineage,
    )
    encoded = encode_header(header)
    path.write_bytes(encoded + bytes(header.body_offset - len(encoded)) + body)

    with (
        Procedure("consume", "1").execute(),
        pytest.raises(ValueError, match="lineage"),
    ):
        BytesArtifact.open(path)


def test_rejects_lineage_digest_different_from_header(
    tmp_path: Path, discovered_catalog: ArtifactCatalog
) -> None:
    path = tmp_path / "lineage-digest.pa"
    reference = ArtifactReference("artifact-1", "example.BytesV1")
    execution = ProcedureExecutionRecord(
        "execution-1", ProcedureRecord("fixture", "1"), outputs=(reference,)
    )
    lineage = ArtifactLineage.for_execution(
        execution,
        (ArtifactRecord(reference, "different-digest", execution.identity),),
    )
    body = b"value"
    header = ArtifactHeader(
        artifact_identifier=reference.artifact_identifier,
        artifact_identity=reference.identity,
        body_offset=4096,
        body_length=len(body),
        body_digest=hashlib.sha256(body).hexdigest(),
        lineage=lineage,
    )
    encoded = encode_header(header)
    path.write_bytes(encoded + bytes(header.body_offset - len(encoded)) + body)

    with (
        Procedure("consume", "1").execute(),
        pytest.raises(ValueError, match="lineage body digest"),
    ):
        BytesArtifact.open(path)


def test_reader_is_invalid_after_owning_context_exits(
    tmp_path: Path, discovered_catalog: ArtifactCatalog
) -> None:
    path = tmp_path / "value.pa"
    write_artifact(path, b"value", identity="artifact-1")

    with Procedure("consume", "1").execute():
        reader = BytesArtifact.open(path)

    with (
        Procedure("later", "1").execute(),
        pytest.raises(RuntimeError, match="context"),
    ):
        reader.body.read()


def test_reader_construction_failure_preserves_error(
    tmp_path: Path, discovered_catalog: ArtifactCatalog
) -> None:
    path = tmp_path / "broken-reader.pa"
    write_artifact(
        path,
        b"value",
        identity="broken-1",
        identifier="example.BrokenV1",
    )

    with (
        Procedure("consume", "1").execute(),
        pytest.raises(RuntimeError, match="construction failed"),
    ):
        open_artifact(path)
