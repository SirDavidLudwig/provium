"""Inspect artifact container metadata."""

from __future__ import annotations

import json
from argparse import ArgumentParser, Namespace
from pathlib import Path

from provium.artifact.discovery import discover_catalogs
from provium.artifact.header import ArtifactHeader, decode_header
from provium.artifact.reader import INSPECTION_UNAVAILABLE
from provium.provenance import ArtifactReference
from provium.session import session

from ..command import CommandContext


def inspect_artifact(path: Path) -> ArtifactHeader:
    """Read an artifact header without loading an artifact-specific reader."""
    return decode_header(path.read_bytes())


def _count_label(count: int, singular: str) -> str:
    suffix = "" if count == 1 else "s"
    return f"{count} {singular}{suffix}"


def _render_inspection(value: object) -> str:
    try:
        return json.dumps(value, default=repr, ensure_ascii=False, indent=2)
    except (TypeError, ValueError):
        return repr(value)


class InspectCommand:
    """Display generic metadata embedded in an artifact container."""

    name = "inspect"
    help = "Inspect a Provium artifact"

    def configure(self, parser: ArgumentParser) -> None:
        parser.add_argument("path", type=Path)
        parser.add_argument(
            "--body",
            action="store_true",
            help="inspect the artifact body when its reader is available",
        )

    def execute(self, arguments: Namespace, context: CommandContext) -> int:
        path: Path = arguments.path
        header = inspect_artifact(path)
        reference = ArtifactReference(
            header.artifact_identity,
            header.artifact_identifier,
        )
        procedure = header.lineage.producing_execution(reference).procedure
        artifact_count = len(header.lineage.artifacts)
        execution_count = len(header.lineage.executions)

        print(f"Path: {path}", file=context.stdout)
        print(f"Artifact type: {header.artifact_identifier}", file=context.stdout)
        print(f"Artifact identity: {header.artifact_identity}", file=context.stdout)
        print(f"Body size: {header.body_length} bytes", file=context.stdout)
        print(f"SHA-256: {header.body_digest}", file=context.stdout)
        print(f"Produced by: {procedure.name} {procedure.version}", file=context.stdout)
        print(
            "Lineage: "
            f"{_count_label(artifact_count, 'artifact')}, "
            f"{_count_label(execution_count, 'execution')}",
            file=context.stdout,
        )
        if arguments.body:
            self._inspect_body(path, header, context)
        return 0

    def _inspect_body(
        self, path: Path, header: ArtifactHeader, context: CommandContext
    ) -> None:
        try:
            definition = discover_catalogs().resolve(header.artifact_identifier)
        except KeyError:
            print(
                "\nBody inspection unavailable: artifact type could not be located.",
                file=context.stdout,
            )
            return

        with session():
            reader = definition.resolve().open(path)
            inspected = reader.inspect()

        if inspected is INSPECTION_UNAVAILABLE:
            print(
                "\nBody inspection unavailable: artifact type does not provide an "
                "inspector.",
                file=context.stdout,
            )
            return

        print("\nInspected body:", file=context.stdout)
        print(_render_inspection(inspected), file=context.stdout)


__all__ = ["InspectCommand", "inspect_artifact"]
