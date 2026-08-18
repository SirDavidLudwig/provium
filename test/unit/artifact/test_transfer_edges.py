from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from provium import Artifact, ArtifactReader, ArtifactWriter
from provium.artifact import transfer


def test_artifact_without_transfer_hooks_reports_unsupported(tmp_path: Path) -> None:
    assert not hasattr(ArtifactReader, "dump")
    assert not hasattr(ArtifactWriter, "load")
    artifact = Artifact("Plain", ArtifactReader, ArtifactWriter)
    assert artifact.dump is None
    assert artifact.load is None


@pytest.mark.parametrize("value", ["invalid", 1])
def test_manifest_rejects_invalid_json_and_shapes(
    tmp_path: Path, value: object
) -> None:
    path = tmp_path / "dump"
    path.mkdir()
    (path / "manifest.json").write_text(
        "{" if value == "invalid" else json.dumps(value)
    )
    result = transfer.verify_dump(path)
    assert not result.valid


def test_manifest_rejects_unsupported_version(tmp_path: Path) -> None:
    path = tmp_path / "dump"
    path.mkdir()
    (path / "manifest.json").write_text(
        json.dumps({"format": "provium-artifact-dump", "version": 2})
    )
    with pytest.raises(ValueError, match="unsupported"):
        transfer.inspect_dump(path)


def test_verification_rejects_malformed_unsafe_and_missing_files(
    tmp_path: Path,
) -> None:
    path = tmp_path / "dump"
    path.mkdir()
    manifest = {
        "format": "provium-artifact-dump",
        "version": 1,
        "representation": {
            "kind": "raw",
            "files": [
                {"path": "../escape", "size": 0, "digest": "x"},
                {"path": "missing", "size": 0, "digest": "x"},
            ],
        },
    }
    (path / "manifest.json").write_text(json.dumps(manifest))
    result = transfer.verify_dump(path)
    assert not result.valid
    assert len(result.errors) == 2

    manifest.pop("representation")
    (path / "manifest.json").write_text(json.dumps(manifest))
    assert not transfer.verify_dump(path).valid


def test_prepare_directory_overwrites_file_and_directory(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.write_text("file")
    transfer._prepare_directory(target, True)
    assert target.is_dir()
    (target / "child").write_text("x")
    transfer._prepare_directory(target, True)
    assert list(target.iterdir()) == []


def test_public_argument_validation(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="representation"):
        transfer.dump_artifact("missing", tmp_path, representation="bad")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="mode"):
        transfer.load_artifact(tmp_path, "output", mode="bad")  # type: ignore[arg-type]


def test_container_validation_and_missing_registration(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "artifact.pa"
    path.write_bytes(b"abc")

    class Header:
        body_offset = 2
        body_length = 10

    monkeypatch.setattr(transfer, "decode_header", lambda data: Header())
    with pytest.raises(ValueError, match="truncated"):
        transfer._read_container(path)

    Header.body_offset = 0
    Header.body_length = 3
    Header.body_digest = "wrong"
    with pytest.raises(ValueError, match="body digest"):
        transfer._read_container(path)

    Header.body_digest = hashlib.sha256(b"abc").hexdigest()
    Header.artifact_identity = "identity"
    Header.artifact_identifier = "identifier"

    class Lineage:
        @staticmethod
        def artifact(reference):
            return type("Record", (), {"body_digest": "wrong"})()

    Header.lineage = Lineage()
    with pytest.raises(ValueError, match="lineage body digest"):
        transfer._read_container(path)

    class Catalog:
        @staticmethod
        def resolve(identifier):
            raise KeyError(identifier)

    monkeypatch.setattr(transfer, "discover_catalogs", lambda: Catalog())
    assert transfer._registration("missing") is None


def test_empty_custom_dump_is_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class Reader(ArtifactReader):
        def __init__(self, region, header) -> None:
            pass

        def close(self) -> None:
            pass

    def empty_dump(reader, destination: Path) -> None:
        pass

    def empty_load(source: Path, writer) -> None:
        pass

    EmptyArtifact = Artifact(
        "Empty", Reader, ArtifactWriter, dump=empty_dump, load=empty_load
    )  # type: ignore[arg-type]

    class Registration:
        artifact = EmptyArtifact

    header = type("Header", (), {"artifact_identifier": "identifier"})()
    monkeypatch.setattr(transfer, "_read_container", lambda path: (header, b"body"))
    monkeypatch.setattr(transfer, "_registration", lambda identifier: Registration())
    with pytest.raises(ValueError, match="no files"):
        transfer.dump_artifact("source", tmp_path / "dump")


def test_custom_import_requires_definition_and_loader(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    manifest = {"artifact": {"identifier": "missing"}}
    monkeypatch.setattr(transfer, "_registration", lambda identifier: None)
    with pytest.raises(ValueError, match="unavailable"):
        transfer._custom_body(manifest, tmp_path)

    ArtifactWithoutLoad = Artifact("No Load", ArtifactReader, ArtifactWriter)

    class Registration:
        artifact = ArtifactWithoutLoad

    monkeypatch.setattr(transfer, "_registration", lambda identifier: Registration())
    with pytest.raises(ValueError, match="custom load"):
        transfer._custom_body(manifest, tmp_path)


def test_write_container_destination_and_header_limits(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    output = tmp_path / "output.pa"
    output.write_bytes(b"existing")
    with pytest.raises(FileExistsError):
        transfer._write_container(output, object(), b"", False)  # type: ignore[arg-type]

    class Header:
        body_offset = 0

    monkeypatch.setattr(transfer, "encode_header", lambda header: b"too large")
    with pytest.raises(ValueError, match="header region"):
        transfer._write_container(output, Header(), b"", True)  # type: ignore[arg-type]
