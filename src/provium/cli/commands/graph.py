"""Render an artifact's lineage graph."""

from __future__ import annotations

from argparse import ArgumentParser, Namespace
from pathlib import Path

from provium.tool.visualization import (
    lineage_to_dot,
    lineage_to_mermaid,
    render_lineage,
    render_mermaid,
)

from ..command import CommandContext
from .inspect import inspect_artifact


class GraphCommand:
    """Write a rendered lineage graph to an image file."""

    name = "graph"
    help = "Render an artifact lineage graph"

    def configure(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--renderer",
            choices=("graphviz", "mermaid"),
            default="mermaid",
        )
        parser.add_argument("artifact", type=Path)
        parser.add_argument("output", type=Path)

    def execute(self, arguments: Namespace, context: CommandContext) -> int:
        output: Path = arguments.output
        if not output.suffix:
            raise ValueError("graph output path requires a format extension")
        header = inspect_artifact(arguments.artifact)
        format = output.suffix[1:].lower()
        if format == "dot":
            if arguments.renderer != "graphviz":
                raise ValueError(".dot output requires graphviz renderer")
            output.write_text(lineage_to_dot(header.lineage))
        elif format == "mmd":
            if arguments.renderer != "mermaid":
                raise ValueError(".mmd output requires mermaid renderer")
            output.write_text(lineage_to_mermaid(header.lineage))
        elif format in {"pdf", "png", "svg"}:
            render = (
                render_lineage
                if arguments.renderer == "graphviz"
                else render_mermaid
            )
            output.write_bytes(render(header.lineage, format=format))
        else:
            raise ValueError(f"unsupported graph output format: .{format}")
        return 0


__all__ = ["GraphCommand"]
