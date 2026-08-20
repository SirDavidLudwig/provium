"""Artifact import and export commands."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from provium import (
    ImperativeProcedure,
    discover_artifact_catalogs,
    read_artifact_header,
    session,
)

from ..command import Command

_LOAD_PROCEDURE_IDENTIFIER = "provium.builtin.LoadArtifactV1"
_LOAD_PROCEDURE_CONTRACT_DIGEST = (
    "17acdbf8b06ab63f7fce758374716414892a81d79fb313f8323013029ff4af24"
)


def _artifact(identifier: str) -> type[Any]:
    try:
        definition = discover_artifact_catalogs().resolve(identifier)
    except KeyError:
        raise ValueError(f"unknown artifact: {identifier}") from None
    return definition.resolve()


class ArtifactCommand(Command):
    """Provide operations for working with artifacts."""

    name = "artifact"
    help = "Manage artifacts"

    def configure(self, parser: argparse.ArgumentParser) -> None:
        actions = parser.add_subparsers(dest="artifact_action", required=True)
        for action in ("dump", "load"):
            action_parser = actions.add_parser(
                action, help=f"{action.title()} an artifact"
            )
            if action == "load":
                action_parser.add_argument("identifier")
            action_parser.add_argument("source", type=Path)
            action_parser.add_argument("destination", type=Path)
            action_parser.set_defaults(artifact_handler=getattr(self, f"_{action}"))

    def execute(self, arguments: argparse.Namespace) -> int:
        try:
            arguments.artifact_handler(arguments)
        except (ImportError, OSError, RuntimeError, TypeError, ValueError) as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        return 0

    @staticmethod
    def _dump(arguments: argparse.Namespace) -> None:
        identifier = read_artifact_header(arguments.source).artifact_identifier
        artifact = _artifact(identifier)
        handler = artifact.dump
        if handler is None:
            raise ValueError(f"artifact {identifier} does not define a dump handler")
        with session():
            with artifact.bind_read(arguments.source).open() as reader:
                handler(reader, arguments.destination)

    @staticmethod
    def _load(arguments: argparse.Namespace) -> None:
        artifact = _artifact(arguments.identifier)
        handler = artifact.load
        if handler is None:
            raise ValueError(
                f"artifact {arguments.identifier} does not define a load handler"
            )
        binding = artifact.bind_write(arguments.destination)
        procedure = ImperativeProcedure(
            _LOAD_PROCEDURE_IDENTIFIER,
            _LOAD_PROCEDURE_CONTRACT_DIGEST,
        )
        with procedure.execute(outputs={"artifact": binding}):
            with binding.open() as writer:
                handler(writer, arguments.source)


__all__ = ["ArtifactCommand"]
