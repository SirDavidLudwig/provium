"""Inspect artifact container metadata."""

from __future__ import annotations

from argparse import ArgumentParser, Namespace
from pathlib import Path

from provium.artifact.header import ArtifactHeader, decode_header
from provium.provenance import ArtifactReference

from ..command import CommandContext


def inspect_artifact(path: Path) -> ArtifactHeader:
    """Read an artifact header without loading an artifact-specific reader."""
    return decode_header(path.read_bytes())


def _count_label(count: int, singular: str) -> str:
    suffix = "" if count == 1 else "s"
    return f"{count} {singular}{suffix}"


class InspectCommand:
    """Display generic metadata embedded in an artifact container."""

    name = "inspect"
    help = "Inspect a Provium artifact"

    def configure(self, parser: ArgumentParser) -> None:
        parser.add_argument("path", type=Path)

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
        return 0


__all__ = ["InspectCommand", "inspect_artifact"]

