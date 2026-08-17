"""Portable artifact dump packages and integrity-preserving imports."""

from __future__ import annotations

import hashlib
import io
import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from ..context import activate_context
from ..provenance import (
    ArtifactLineage,
    ArtifactRecord,
    ArtifactReference,
    ProcedureExecutionRecord,
    ProcedureRecord,
)
from .definition import Artifact
from .discovery import discover_catalogs
from .header import ArtifactHeader, decode_header, encode_header
from .region import BodyRegion

Representation = Literal["auto", "custom", "raw"]
ImportMode = Literal["exact", "derived", "root"]


@dataclass(frozen=True, slots=True)
class DumpResult:
    destination: Path
    representation: str
    manifest: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ImportResult:
    destination: Path
    integrity: Literal["exact", "modified"]
    identity_preserved: bool


@dataclass(frozen=True, slots=True)
class VerificationResult:
    valid: bool
    errors: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DumpInfo:
    artifact_identifier: str
    original_body_digest: str
    representation: str
    events: tuple[dict[str, Any], ...]


class _Owner:
    active = True

    def _owns_active_context(self) -> bool:
        return self.active


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _event(kind: str, **details: Any) -> dict[str, Any]:
    return {
        "kind": kind,
        "timestamp": datetime.now(UTC).isoformat(),
        **details,
    }


def _read_container(path: Path) -> tuple[ArtifactHeader, bytes]:
    data = path.read_bytes()
    header = decode_header(data)
    end = header.body_offset + header.body_length
    if end > len(data):
        raise ValueError("artifact body is truncated")
    body = data[header.body_offset : end]
    if _digest(body) != header.body_digest:
        raise ValueError("artifact body digest does not match")
    reference = ArtifactReference(header.artifact_identity, header.artifact_identifier)
    if header.lineage.artifact(reference).body_digest != header.body_digest:
        raise ValueError("artifact lineage body digest does not match header")
    return header, body


def _registration(identifier: str) -> Any | None:
    try:
        return discover_catalogs().resolve(identifier)
    except KeyError:
        return None


def _prepare_directory(path: Path, overwrite: bool) -> None:
    if path.exists():
        if not overwrite:
            raise FileExistsError(f"destination already exists: {path}")
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    path.mkdir(parents=True)


def _file_records(root: Path) -> list[dict[str, Any]]:
    records = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        data = path.read_bytes()
        records.append(
            {
                "path": path.relative_to(root).as_posix(),
                "size": len(data),
                "digest": _digest(data),
            }
        )
    return records


def dump_artifact(
    source: str | Path,
    destination: str | Path,
    *,
    representation: Representation = "auto",
    overwrite: bool = False,
) -> DumpResult:
    """Dump an artifact into a portable directory package."""
    if representation not in {"auto", "custom", "raw"}:
        raise ValueError(f"invalid representation: {representation}")
    source_path, destination_path = Path(source), Path(destination)
    header, body = _read_container(source_path)
    registration = _registration(header.artifact_identifier)
    artifact_type = None if registration is None else registration.artifact
    reader_type = None if artifact_type is None else artifact_type._resolve_reader()
    custom = (
        artifact_type is not None
        and artifact_type.dump.__func__ is not Artifact.dump.__func__
        and artifact_type.load.__func__ is not Artifact.load.__func__
    )
    if representation == "custom" and not custom:
        raise ValueError("custom dump is not supported for this artifact")
    selected = "custom" if representation != "raw" and custom else "raw"
    _prepare_directory(destination_path, overwrite)
    if selected == "custom":
        payload = destination_path / "payload"
        payload.mkdir()
        owner = _Owner()
        region = BodyRegion(io.BytesIO(body), 0, len(body), owner)
        reader = reader_type(region, header)
        with activate_context(owner):
            artifact_type.dump(reader, payload)
            reader.close()
        files = _file_records(payload)
        if not files:
            raise ValueError("custom dump produced no files")
    else:
        (destination_path / "body.dat").write_bytes(body)
        files = _file_records(destination_path)
    manifest = {
        "format": "provium-artifact-dump",
        "version": 1,
        "artifact": {
            "identifier": header.artifact_identifier,
            "identity": header.artifact_identity,
            "body_digest": header.body_digest,
            "body_length": header.body_length,
            "body_offset": header.body_offset,
            "lineage": header.lineage.to_dict(),
        },
        "representation": {"kind": selected, "files": files},
        "events": [_event("dump")],
    }
    (destination_path / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    return DumpResult(destination_path, selected, manifest)


def _load_manifest(path: Path) -> dict[str, Any]:
    try:
        manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ValueError("invalid dump manifest") from error
    if (
        not isinstance(manifest, dict)
        or manifest.get("format") != "provium-artifact-dump"
        or manifest.get("version") != 1
    ):
        raise ValueError("unsupported dump manifest")
    return manifest


def verify_dump(source: str | Path) -> VerificationResult:
    """Verify the structure and file digests of a dump package."""
    path = Path(source)
    try:
        manifest = _load_manifest(path)
        files = manifest["representation"]["files"]
        errors = []
        for record in files:
            relative = Path(record["path"])
            if relative.is_absolute() or ".." in relative.parts:
                errors.append(f"unsafe payload path: {relative}")
                continue
            candidate = (
                path
                / ("payload" if manifest["representation"]["kind"] == "custom" else "")
                / relative
            )
            if not candidate.is_file():
                errors.append(f"missing payload file: {relative}")
                continue
            data = candidate.read_bytes()
            if len(data) != record["size"] or _digest(data) != record["digest"]:
                errors.append(f"payload digest mismatch: {relative}")
        return VerificationResult(not errors, tuple(errors))
    except (KeyError, TypeError, ValueError) as error:
        return VerificationResult(False, (str(error),))


def inspect_dump(source: str | Path) -> DumpInfo:
    """Return summary metadata for a dump package."""
    manifest = _load_manifest(Path(source))
    return DumpInfo(
        manifest["artifact"]["identifier"],
        manifest["artifact"]["body_digest"],
        manifest["representation"]["kind"],
        tuple(manifest["events"]),
    )


def _custom_body(manifest: dict[str, Any], source: Path) -> bytes:
    identifier = manifest["artifact"]["identifier"]
    registration = _registration(identifier)
    if registration is None:
        raise ValueError(f"artifact definition is unavailable: {identifier}")
    artifact_type = registration.artifact
    if artifact_type.load.__func__ is Artifact.load.__func__:
        raise ValueError("custom load is not supported for this artifact")
    writer_type = artifact_type._resolve_writer()
    owner = _Owner()
    stream = io.BytesIO()
    writer = writer_type(
        BodyRegion(stream, 0, 0, owner, writable=True),
        _manifest_header(manifest),
    )
    with activate_context(owner):
        artifact_type.load(source / "payload", writer)
        length = writer.body.length
        writer.close()
    return stream.getvalue()[:length]


def _manifest_header(manifest: dict[str, Any]) -> ArtifactHeader:
    artifact = manifest["artifact"]
    return ArtifactHeader(
        artifact_identifier=artifact["identifier"],
        artifact_identity=artifact["identity"],
        body_offset=artifact["body_offset"],
        body_length=artifact["body_length"],
        body_digest=artifact["body_digest"],
        lineage=ArtifactLineage.from_dict(artifact["lineage"]),
    )


def _write_container(
    path: Path, header: ArtifactHeader, body: bytes, overwrite: bool
) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"destination already exists: {path}")
    encoded = encode_header(header)
    if len(encoded) > header.body_offset:
        raise ValueError("artifact lineage exceeds the available header region")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary.write_bytes(encoded + bytes(header.body_offset - len(encoded)) + body)
    temporary.replace(path)


def _changed_header(
    original: ArtifactHeader, body: bytes, mode: ImportMode
) -> ArtifactHeader:
    reference = ArtifactReference(str(uuid4()), original.artifact_identifier)
    execution_identity = str(uuid4())
    original_reference = ArtifactReference(
        original.artifact_identity, original.artifact_identifier
    )
    procedure = ProcedureRecord(
        "provium.import" if mode == "derived" else "provium.unsafe-import", "1"
    )
    execution = ProcedureExecutionRecord(
        execution_identity,
        procedure,
        (original_reference,) if mode == "derived" else (),
        (reference,),
    )
    record = ArtifactRecord(reference, _digest(body), execution_identity)
    lineage = ArtifactLineage.for_execution(
        execution,
        (record,),
        (original.lineage,) if mode == "derived" else (),
    )
    return ArtifactHeader(
        original.artifact_identifier,
        reference.identity,
        original.body_offset,
        len(body),
        record.body_digest,
        lineage,
    )


def import_artifact(
    source: str | Path,
    destination: str | Path,
    *,
    mode: ImportMode = "exact",
    representation: Representation = "auto",
    overwrite: bool = False,
) -> ImportResult:
    """Import a dump, preserving identity unless modified content is allowed."""
    if mode not in {"exact", "derived", "root"}:
        raise ValueError(f"invalid import mode: {mode}")
    source_path, destination_path = Path(source), Path(destination)
    verification = verify_dump(source_path)
    if not verification.valid:
        raise ValueError(f"dump verification failed: {verification.errors[0]}")
    manifest = _load_manifest(source_path)
    kind = manifest["representation"]["kind"]
    if representation != "auto" and representation != kind:
        raise ValueError(f"dump representation is {kind}, not {representation}")
    body = (
        _custom_body(manifest, source_path)
        if kind == "custom"
        else (source_path / "body.dat").read_bytes()
    )
    original = _manifest_header(manifest)
    exact = _digest(body) == original.body_digest and len(body) == original.body_length
    if not exact and mode == "exact":
        raise ValueError("imported body differs from the original artifact")
    header = original if exact else _changed_header(original, body, mode)
    _write_container(destination_path, header, body, overwrite)
    manifest["events"].append(
        _event("import", mode=mode, integrity="exact" if exact else "modified")
    )
    (source_path / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    return ImportResult(destination_path, "exact" if exact else "modified", exact)


__all__ = [
    "DumpInfo",
    "DumpResult",
    "ImportResult",
    "VerificationResult",
    "dump_artifact",
    "import_artifact",
    "inspect_dump",
    "verify_dump",
]
