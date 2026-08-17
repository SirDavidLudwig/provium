"""Dump, import, inspect, and verify portable artifact packages."""

from __future__ import annotations

from argparse import ArgumentParser, Namespace
from pathlib import Path

from provium.artifact.transfer import (
    dump_artifact,
    import_artifact,
    inspect_dump,
    verify_dump,
)

from ..command import CommandContext


class ArtifactCommand:
    """Manage portable artifact dump packages."""

    name = "artifact"
    help = "Manage portable artifact packages"

    def configure(self, parser: ArgumentParser) -> None:
        commands = parser.add_subparsers(dest="artifact_command", required=True)
        dump = commands.add_parser("dump")
        dump.add_argument("source", type=Path)
        dump.add_argument("destination", type=Path)
        dump.add_argument(
            "--representation", choices=("auto", "custom", "raw"), default="auto"
        )
        dump.add_argument("--overwrite", action="store_true")

        load = commands.add_parser("import")
        load.add_argument("source", type=Path)
        load.add_argument("destination", type=Path)
        load.add_argument(
            "--mode", choices=("exact", "derived", "root"), default="exact"
        )
        load.add_argument(
            "--representation", choices=("auto", "custom", "raw"), default="auto"
        )
        load.add_argument("--overwrite", action="store_true")

        inspect = commands.add_parser("inspect-dump")
        inspect.add_argument("source", type=Path)
        verify = commands.add_parser("verify-dump")
        verify.add_argument("source", type=Path)

    def execute(self, arguments: Namespace, context: CommandContext) -> int:
        if arguments.artifact_command == "dump":
            result = dump_artifact(
                arguments.source,
                arguments.destination,
                representation=arguments.representation,
                overwrite=arguments.overwrite,
            )
            print(
                f"Dumped {result.representation} package to {result.destination}",
                file=context.stdout,
            )
            return 0
        if arguments.artifact_command == "import":
            result = import_artifact(
                arguments.source,
                arguments.destination,
                mode=arguments.mode,
                representation=arguments.representation,
                overwrite=arguments.overwrite,
            )
            print(
                f"Imported {result.integrity} artifact to {result.destination}",
                file=context.stdout,
            )
            return 0
        if arguments.artifact_command == "inspect-dump":
            info = inspect_dump(arguments.source)
            print(f"Artifact type: {info.artifact_identifier}", file=context.stdout)
            print(f"SHA-256: {info.original_body_digest}", file=context.stdout)
            print(f"Representation: {info.representation}", file=context.stdout)
            print(f"Transfer events: {len(info.events)}", file=context.stdout)
            return 0
        result = verify_dump(arguments.source)
        if result.valid:
            print("Dump verified", file=context.stdout)
            return 0
        for error in result.errors:
            print(error, file=context.stderr)
        return 1


__all__ = ["ArtifactCommand"]
